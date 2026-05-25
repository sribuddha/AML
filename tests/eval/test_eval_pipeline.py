"""E2E test for the full eval pipeline: upload → workflow → evaluation."""

import json
import uuid
from datetime import datetime, UTC
from pathlib import Path

import pytest
from sqlalchemy import select

from src.aml_workflow.eval import EvalReport, PatternMetrics, _compute_metrics
from src.aml_workflow.eval.hallucination import check_sar as check_hallucination
from src.aml_workflow.eval.completeness import check_sar as check_completeness
from src.aml_workflow.triggers import run_validation
from src.aml_workflow.models.rule import Rule
from src.aml_workflow.models.validation_result import ValidationResult
from src.file_processor.models import Transaction, UploadedFiles
from tests.helpers import upload_csv


@pytest.fixture
def fraud_csv_path(tmp_path: Path) -> Path:
    """Create a mini fraud dataset CSV for testing."""
    from scripts.test_generate_fraud_data import (
        generate_structuring_set,
        generate_impossible_travel_pair,
    )

    rows = []
    manifest = {}
    # Some clean rows
    for i in range(20):
        rows.append({
            "account_id": "ACC001",
            "customer_id": "CUST001",
            "amount": f"{round(100 + i * 50, 2):.2f}",
            "counterparty": "Acme Corp",
            "location": "New York",
            "date": "2026-06-01",
            "source_txn_id": f"CLEAN{i:04d}",
        })

    # Structuring pattern
    struct_rows = generate_structuring_set("ACC001", "CUST001", 5)
    for r in struct_rows:
        rows.append(r)
        manifest[r["source_txn_id"]] = r["ground_truth"]
    # Impossible travel pattern
    travel_rows = generate_impossible_travel_pair("ACC002", "CUST002", 10)
    for r in travel_rows:
        rows.append(r)
        manifest[r["source_txn_id"]] = r["ground_truth"]

    path = tmp_path / "fraud_test.csv"
    import csv
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "account_id", "customer_id", "amount", "counterparty",
            "location", "date", "source_txn_id",
        ])
        writer.writeheader()
        for row in rows:
            out = {k: row[k] for k in writer.fieldnames}
            writer.writerow(out)

    manifest_path = tmp_path / "fraud_test.manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f)

    return path, manifest_path


@pytest.mark.asyncio
class TestEvalPipeline:
    async def test_eval_pipeline_end_to_end(self, seeded_session, fraud_csv_path, engine):
        csv_path, manifest_path = fraud_csv_path

        # Seed a rule so some txns get flagged
        now = datetime.now(UTC).isoformat()
        rule = Rule(
            id=str(uuid.uuid4()), name="High Value Check",
            type="deterministic", status="active",
            rules_json='[{"field": "amount", "operator": ">", "value": 10000}]',
            created_at=now, updated_at=now,
        )
        seeded_session.add(rule)
        await seeded_session.commit()

        # Upload
        upload_id = await upload_csv(seeded_session, csv_path)

        # Run workflow (fallback — no API keys)
        await run_validation(upload_id, seeded_session)

        # Load manifest
        with open(manifest_path) as f:
            manifest: dict[str, str] = json.load(f)

        # Check validation results
        vrs = (await seeded_session.execute(
            select(ValidationResult).where(ValidationResult.upload_id == upload_id)
        )).scalars().all()
        assert len(vrs) > 0

        # Get transactions
        txns = (await seeded_session.execute(
            select(Transaction).where(Transaction.upload_id == upload_id)
        )).scalars().all()
        txn_by_src = {t.source_txn_id: t for t in txns}
        txn_by_id = {t.id: t for t in txns}
        flagged_ids = {vr.transaction_id for vr in vrs if vr.status == "flagged"}

        # ── Compute pattern metrics ─────────────────────────────
        pattern_gt: dict[str, set[str]] = {}
        for src_id, pattern in manifest.items():
            pattern_gt.setdefault(pattern, set()).add(src_id)

        metrics = []
        for pattern, src_ids in pattern_gt.items():
            total = len(src_ids)
            flagged = sum(
                1 for src_id in src_ids
                if src_id in txn_by_src and txn_by_src[src_id].id in flagged_ids
            )
            prec, rec, f1 = _compute_metrics(total, flagged)
            metrics.append(PatternMetrics(
                pattern=pattern, total=total, flagged=flagged,
                precision=prec, recall=rec, f1=f1,
            ))

        assert len(metrics) > 0
        for m in metrics:
            assert m.total > 0
            assert 0.0 <= m.precision <= 1.0
            assert 0.0 <= m.recall <= 1.0

    async def test_compute_metrics_zero_total(self):
        prec, rec, f1 = _compute_metrics(0, 0)
        assert prec == 0.0
        assert rec == 0.0
        assert f1 == 0.0

    async def test_pattern_metrics_accuracy_property(self):
        pm = PatternMetrics(pattern="test", total=10, flagged=5, precision=0.5, recall=0.8, f1=0.62)
        assert pm.accuracy == pm.recall

    async def test_eval_report_summary_format(self):
        pm = PatternMetrics(pattern="structuring", total=10, flagged=5, precision=0.5, recall=0.8, f1=0.62)
        report = EvalReport(
            upload_id="test-upload-id",
            total_transactions=100,
            total_anomalous=10,
            total_flagged=5,
            pattern_metrics=[pm],
            overall_precision=0.5,
            overall_recall=0.8,
            overall_f1=0.62,
            hallucination_free_rate=1.0,
            avg_completeness=0.95,
        )
        text = report.summary()
        assert "test-upl" in text
        assert "100" in text
        assert "structuring" in text

    async def test_hallucination_on_workflow_sars(self, seeded_session, fraud_csv_path):
        """Run the full workflow and check all generated SARs for hallucination."""
        csv_path, manifest_path = fraud_csv_path

        now = datetime.now(UTC).isoformat()
        rule = Rule(
            id=str(uuid.uuid4()), name="High Value Check",
            type="deterministic", status="active",
            rules_json='[{"field": "amount", "operator": ">", "value": 10000}]',
            created_at=now, updated_at=now,
        )
        seeded_session.add(rule)
        await seeded_session.commit()

        upload_id = await upload_csv(seeded_session, csv_path)
        await run_validation(upload_id, seeded_session)

        from src.aml_workflow.models.sar import SAR
        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()

        txns = (await seeded_session.execute(
            select(Transaction).where(Transaction.upload_id == upload_id)
        )).scalars().all()
        txn_by_id = {t.id: t for t in txns}

        vrs = (await seeded_session.execute(
            select(ValidationResult).where(ValidationResult.upload_id == upload_id)
        )).scalars().all()
        flag_by_txn = {vr.transaction_id: vr.flag_details for vr in vrs if vr.status == "flagged"}

        for sar in sars:
            txn = txn_by_id.get(sar.transaction_id)
            assert txn is not None, f"Transaction {sar.transaction_id} not found for SAR {sar.id}"

            # Collect other same-customer transactions — the LLM prompt includes
            # these as context, so amounts from related transactions are legitimate
            related_txns = [
                {
                    "source_txn_id": rt.source_txn_id,
                    "amount": rt.amount,
                    "counterparty": rt.counterparty,
                }
                for rt in txns
                if rt.id != sar.transaction_id and rt.customer_id == txn.customer_id
            ]

            txn_dict = {
                "source_txn_id": txn.source_txn_id,
                "account_id": txn.account_id,
                "amount": txn.amount,
                "counterparty": txn.counterparty,
                "city": txn.city, "state": txn.state, "country": txn.country,
                "date": txn.date,
            }
            hl = await check_hallucination(
                sar.id, sar.transaction_id, sar.content, txn_dict,
                flag_by_txn.get(sar.transaction_id),
                related_transactions=related_txns,
            )
            assert hl.passed, f"SAR {sar.id}: hallucinated facts: {hl.hallucinated_facts}"

    async def test_completeness_on_workflow_sars(self, seeded_session, fraud_csv_path):
        """Check all generated SARs cover their triggered rules."""
        csv_path, _ = fraud_csv_path

        now = datetime.now(UTC).isoformat()
        rule = Rule(
            id=str(uuid.uuid4()), name="High Value Check",
            type="deterministic", status="active",
            rules_json='[{"field": "amount", "operator": ">", "value": 10000}]',
            created_at=now, updated_at=now,
        )
        seeded_session.add(rule)
        await seeded_session.commit()

        upload_id = await upload_csv(seeded_session, csv_path)
        await run_validation(upload_id, seeded_session, mode="full")

        from src.aml_workflow.models.sar import SAR
        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()

        vrs = (await seeded_session.execute(
            select(ValidationResult).where(ValidationResult.upload_id == upload_id)
        )).scalars().all()
        flag_by_txn = {vr.transaction_id: vr.flag_details for vr in vrs if vr.status == "flagged"}

        for sar in sars:
            comp = await check_completeness(
                sar.id, sar.transaction_id, sar.content,
                flag_by_txn.get(sar.transaction_id),
            )
            assert comp.score > 0.0, f"SAR {sar.id}: no rules covered"
