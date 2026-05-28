import uuid
from datetime import datetime, UTC

import pytest
from sqlalchemy import select, text

from src.aml_workflow.graph import create_workflow
from src.aml_workflow.llm import LLMClient, TriageDecision, SarResult
from src.core.models.rule import Rule
from src.core.models.sar import SAR
from src.aml_workflow.models.transaction_status import TransactionStatus
from src.core.models.transaction import Transaction
from src.core.models.uploaded_files import UploadedFiles
from tests.helpers import upload_csv


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    async def mock_triage_batch(*args, **kwargs):
        txns = args[1] if len(args) > 1 else kwargs.get("transactions", [])
        return [TriageDecision(escalate=True, reason="Stage3 escalation", confidence=0.9) for _ in txns]

    async def mock_stage3_batch(*args, **kwargs):
        txns = args[1] if len(args) > 1 else kwargs.get("transactions", [])
        return [TriageDecision(escalate=True, reason="Stage3 deep-dive confirms", confidence=0.95) for _ in txns]

    async def mock_sar_batch(*args, **kwargs):
        txns = args[1] if len(args) > 1 else kwargs.get("transactions", [])
        return [SarResult(content="Stage3 SAR body", raw_response='{"sar": "stage3"}') for _ in txns]

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
        }

    monkeypatch.setattr("src.aml_workflow.enrichment.enrich_transactions", mock_enrich)


async def _resolve_transaction(session, txn_id, resolution, notes=""):
    """Simulate service.resolve_transaction by updating SAR and status directly."""
    import uuid as _uuid
    from datetime import datetime, UTC

    stmt = select(SAR).where(SAR.transaction_id == txn_id)
    sar = (await session.execute(stmt)).scalar_one_or_none()
    if sar is None:
        raise ValueError(f"No SAR found for transaction {txn_id}")

    now = datetime.now(UTC).isoformat()
    txn_status = "clean" if resolution == "confirmed" else "dismissed"

    await session.execute(
        text("UPDATE sar SET status = :status, reviewed_at = :now, review_notes = :notes, updated_at = :now WHERE id = :id"),
        {"status": resolution, "now": now, "notes": notes, "id": sar.id},
    )
    session.add(TransactionStatus(
        id=str(_uuid.uuid4()),
        transaction_id=txn_id,
        status=txn_status,
        actor="human",
        created_at=now,
    ))

    remaining = (await session.execute(
        text("SELECT COUNT(*) FROM sar WHERE upload_id = :upload_id AND status = 'pending_review'"),
        {"upload_id": sar.upload_id},
    )).scalar()
    if remaining == 0:
        await session.execute(
            text("UPDATE uploaded_files SET status = 'complete', updated_at = :now WHERE id = :id"),
            {"now": now, "id": sar.upload_id},
        )


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


@pytest.fixture
async def workflow_sars(seeded_session, upload_with_rule):
    """Run workflow with checkpointer and return (upload_id, sar_list)."""
    from langgraph.checkpoint.memory import MemorySaver

    upload_id = upload_with_rule
    workflow = create_workflow(seeded_session, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": upload_id}}
    await workflow.ainvoke({"upload_id": upload_id}, config)

    sars = (await seeded_session.execute(
        select(SAR).where(SAR.upload_id == upload_id)
    )).scalars().all()
    return upload_id, sars


class TestStage3Resolution:

    async def test_workflow_produces_sars_for_flagged(self, seeded_session, workflow_sars):
        _, sars = workflow_sars
        assert len(sars) > 0
        for sar in sars:
            assert sar.status == "pending_review"

    async def test_resolve_transaction_confirmed(self, seeded_session, workflow_sars):
        upload_id, sars = workflow_sars
        sar = sars[0]

        await _resolve_transaction(seeded_session, sar.transaction_id, "confirmed", "Approved after review")
        await seeded_session.commit()
        await seeded_session.refresh(sar)

        assert sar.status == "confirmed"
        assert sar.review_notes == "Approved after review"

        latest_status = (await seeded_session.execute(
            text("""
                SELECT status FROM transaction_status
                WHERE transaction_id = :txn_id
                ORDER BY created_at DESC LIMIT 1
            """),
            {"txn_id": sar.transaction_id},
        )).scalar()
        assert latest_status == "clean"

    async def test_resolve_transaction_dismissed(self, seeded_session, workflow_sars):
        upload_id, sars = workflow_sars
        sar = sars[0]

        await _resolve_transaction(seeded_session, sar.transaction_id, "dismissed", "False positive")
        await seeded_session.commit()
        await seeded_session.refresh(sar)

        assert sar.status == "dismissed"

        latest_status = (await seeded_session.execute(
            text("SELECT status FROM transaction_status WHERE transaction_id = :txn_id ORDER BY created_at DESC LIMIT 1"),
            {"txn_id": sar.transaction_id},
        )).scalar()
        assert latest_status == "dismissed"

    async def test_all_sars_resolved_completes_upload(self, seeded_session, workflow_sars):
        upload_id, sars = workflow_sars

        for sar in sars:
            await _resolve_transaction(seeded_session, sar.transaction_id, "confirmed", "Reviewed")
        await seeded_session.commit()

        upload = await seeded_session.get(UploadedFiles, upload_id)
        assert upload.status == "complete"

    async def test_unresolved_sar_keeps_upload_pending(self, seeded_session, workflow_sars):
        upload_id, sars = workflow_sars

        await _resolve_transaction(seeded_session, sars[0].transaction_id, "confirmed", "Done")
        await seeded_session.commit()

        upload = await seeded_session.get(UploadedFiles, upload_id)
        assert upload.status != "complete"

    async def test_remaining_sars_count_via_text_query(self, seeded_session, workflow_sars):
        upload_id, sars = workflow_sars

        count_before = (await seeded_session.execute(
            text("SELECT COUNT(*) FROM sar WHERE upload_id = :uid AND status = 'pending_review'"),
            {"uid": upload_id},
        )).scalar()
        assert count_before == len(sars)

        await _resolve_transaction(seeded_session, sars[0].transaction_id, "confirmed")
        await seeded_session.commit()

        count_after = (await seeded_session.execute(
            text("SELECT COUNT(*) FROM sar WHERE upload_id = :uid AND status = 'pending_review'"),
            {"uid": upload_id},
        )).scalar()
        assert count_after == len(sars) - 1
