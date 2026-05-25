import uuid
from datetime import datetime, UTC

import pytest
from sqlalchemy import select

from src.aml_workflow.graph import create_workflow
from src.aml_workflow.llm import LLMClient, TriageDecision, SarResult
from src.aml_workflow.models.rule import Rule
from src.aml_workflow.models.transaction_status import TransactionStatus
from src.aml_workflow.models.validation_result import ValidationResult
from src.file_processor.models import Transaction, UploadedFiles
from tests.helpers import upload_csv


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    async def mock_triage_batch(*args, **kwargs):
        txns = args[1] if len(args) > 1 else kwargs.get("transactions", [])
        return [TriageDecision(escalate=True, reason="E2E escalation", confidence=0.9) for _ in txns]

    async def mock_stage3_batch(*args, **kwargs):
        txns = args[1] if len(args) > 1 else kwargs.get("transactions", [])
        return [TriageDecision(escalate=True, reason="E2E stage3 confirms", confidence=0.95) for _ in txns]

    async def mock_sar_batch(*args, **kwargs):
        txns = args[1] if len(args) > 1 else kwargs.get("transactions", [])
        return [SarResult(content="E2E SAR report", raw_response='{"sar": "e2e"}') for _ in txns]

    monkeypatch.setattr(LLMClient, "triage_batch", mock_triage_batch)
    monkeypatch.setattr(LLMClient, "triage_stage3_batch", mock_stage3_batch)
    monkeypatch.setattr(LLMClient, "generate_sar_batch", mock_sar_batch)


@pytest.fixture(autouse=True)
def mock_enrichment(monkeypatch):
    async def mock_enrich(*args, **kwargs):
        return {
            "CUST001": {
                "customer_txn_count_30d": 3,
                "customer_sum_30d": 101000.0,
                "customer_avg_30d": 33666.67,
                "customer_std_amt_30d": None,
                "account_type": "checking",
                "account_age_days": 30,
                "structuring_24h_count": 0,
                "velocity_zscore": None,
                "dormancy_days": 0,
            },
            "CUST002": {
                "customer_txn_count_30d": 2,
                "customer_sum_30d": 25000.0,
                "customer_avg_30d": 12500.0,
                "customer_std_amt_30d": None,
                "account_type": "checking",
                "account_age_days": 30,
                "structuring_24h_count": 0,
                "velocity_zscore": None,
                "dormancy_days": 0,
            },
        }

    monkeypatch.setattr("src.aml_workflow.enrichment.enrich_transactions", mock_enrich)


@pytest.fixture
async def upload_with_rule(seeded_session, sample_csv_path):
    uid = await upload_csv(seeded_session, sample_csv_path)
    now = datetime.now(UTC).isoformat()
    seeded_session.add(Rule(
        id=str(uuid.uuid4()), name="High Value Check",
        type="deterministic", status="active",
        rules_json='[{"field": "amount", "operator": ">", "value": 10000}]',
        created_at=now, updated_at=now,
    ))
    await seeded_session.commit()
    return uid


class TestE2EWorkflow:

    async def test_workflow_processes_all_transactions(self, seeded_session, upload_with_rule):
        upload_id = upload_with_rule
        workflow = create_workflow(seeded_session)
        state = await workflow.ainvoke({"upload_id": upload_id})
        assert len(state["transactions"]) == 6
        assert len(state["results"]) == 6

    async def test_rules_fire_on_high_value_transactions(self, seeded_session, upload_with_rule):
        upload_id = upload_with_rule
        workflow = create_workflow(seeded_session)
        state = await workflow.ainvoke({"upload_id": upload_id})
        flagged = [r for r in state["results"] if r["status"] == "flagged"]
        assert len(flagged) == 2

    async def test_validation_results_persisted_to_database(self, seeded_session, upload_with_rule):
        upload_id = upload_with_rule
        workflow = create_workflow(seeded_session)
        await workflow.ainvoke({"upload_id": upload_id})
        vrs = (await seeded_session.execute(
            select(ValidationResult).where(ValidationResult.upload_id == upload_id)
        )).scalars().all()
        assert len(vrs) == 6
        for vr in vrs:
            assert vr.status in ("clean", "flagged")

    async def test_transaction_audit_trail_created(self, seeded_session, upload_with_rule):
        upload_id = upload_with_rule
        workflow = create_workflow(seeded_session)
        await workflow.ainvoke({"upload_id": upload_id})
        txns = (await seeded_session.execute(
            select(Transaction).where(Transaction.upload_id == upload_id)
        )).scalars().all()
        for txn in txns:
            statuses = (await seeded_session.execute(
                select(TransactionStatus).where(TransactionStatus.transaction_id == txn.id)
            )).scalars().all()
            assert len(statuses) >= 2

    async def test_flagged_transactions_get_risk_level(self, seeded_session, upload_with_rule):
        upload_id = upload_with_rule
        workflow = create_workflow(seeded_session)
        await workflow.ainvoke({"upload_id": upload_id})
        flagged = (await seeded_session.execute(
            select(ValidationResult).where(
                ValidationResult.upload_id == upload_id,
                ValidationResult.status == "flagged",
            )
        )).scalars().all()
        for vr in flagged:
            assert vr.risk_level is not None
            assert vr.risk_level in ("high", "auto_reviewed")

    async def test_upload_status_set_to_pending_human(self, seeded_session, upload_with_rule):
        upload_id = upload_with_rule
        workflow = create_workflow(seeded_session)
        await workflow.ainvoke({"upload_id": upload_id})
        upload = await seeded_session.get(UploadedFiles, upload_id)
        assert upload is not None
        assert upload.status == "pending_human"
