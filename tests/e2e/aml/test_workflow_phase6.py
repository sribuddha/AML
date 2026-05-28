import uuid
from datetime import datetime, UTC

import pytest
from sqlalchemy import select

from src.aml_workflow.graph import create_workflow
from src.aml_workflow.llm import LLMClient, TriageDecision, SarResult
from src.core.models.rule import Rule
from src.core.models.sar import SAR
from src.aml_workflow.models.transaction_status import TransactionStatus
from src.core.models.validation_result import ValidationResult
from src.core.models.transaction import Transaction
from src.core.models.uploaded_files import UploadedFiles
from src.aml_workflow.models.upload_status import UploadStatus
from tests.helpers import upload_csv


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    async def mock_triage_batch(*args, **kwargs):
        txns = args[1] if len(args) > 1 else kwargs.get("transactions", [])
        return [TriageDecision(escalate=True, reason="Phase6 escalation", confidence=0.9) for _ in txns]

    async def mock_stage3_batch(*args, **kwargs):
        txns = args[1] if len(args) > 1 else kwargs.get("transactions", [])
        return [TriageDecision(escalate=True, reason="Phase6 deep-dive confirms", confidence=0.95) for _ in txns]

    async def mock_sar_batch(*args, **kwargs):
        txns = args[1] if len(args) > 1 else kwargs.get("transactions", [])
        return [SarResult(content="Phase6 SAR report body", raw_response='{"sar": "phase6"}') for _ in txns]

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


class TestPhase6Workflow:

    async def test_full_workflow_produces_sars(self, seeded_session, upload_with_rule):
        upload_id = upload_with_rule
        workflow = create_workflow(seeded_session)
        state = await workflow.ainvoke({"upload_id": upload_id})
        assert "sars" in state
        assert len(state["sars"]) > 0

    async def test_sars_persisted_with_correct_status(self, seeded_session, upload_with_rule):
        upload_id = upload_with_rule
        workflow = create_workflow(seeded_session)
        await workflow.ainvoke({"upload_id": upload_id})
        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        assert len(sars) == 2
        for sar in sars:
            assert sar.status == "pending_review"
            assert sar.content == "Phase6 SAR report body"

    async def test_flagged_transactions_escalated_to_high_risk(self, seeded_session, upload_with_rule):
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
            assert vr.risk_level == "high"

    async def test_upload_status_set_to_pending_human(self, seeded_session, upload_with_rule):
        upload_id = upload_with_rule
        workflow = create_workflow(seeded_session)
        await workflow.ainvoke({"upload_id": upload_id})
        upload = await seeded_session.get(UploadedFiles, upload_id)
        assert upload.status == "pending_human"

    async def test_sar_node_sets_pending_review_status(self, seeded_session, upload_with_rule):
        upload_id = upload_with_rule
        workflow = create_workflow(seeded_session)
        await workflow.ainvoke({"upload_id": upload_id})

        sar_txn_ids = (await seeded_session.execute(
            select(SAR.transaction_id).where(SAR.upload_id == upload_id)
        )).scalars().all()
        assert len(sar_txn_ids) == 2

        statuses = (await seeded_session.execute(
            select(TransactionStatus).where(
                TransactionStatus.transaction_id.in_(sar_txn_ids),
                TransactionStatus.status == "pending_review",
            )
        )).scalars().all()
        assert len(statuses) >= 2

    async def test_human_review_resume_completes_workflow(self, seeded_session, upload_with_rule):
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.types import Command

        upload_id = upload_with_rule
        workflow = create_workflow(seeded_session, checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": upload_id}}

        result = await workflow.ainvoke({"upload_id": upload_id}, config)
        assert "__interrupt__" in result

        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        for sar in sars:
            sar.status = "confirmed"
            sar.reviewed_at = datetime.now(UTC).isoformat()
            sar.review_notes = "Approved in E2E"
        await seeded_session.commit()

        final = await workflow.ainvoke(Command(resume="all_reviewed"), config)
        assert "__interrupt__" not in final
        assert final.get("human_review_complete") is True
        upload = await seeded_session.get(UploadedFiles, upload_id)
        assert upload.status == "complete"

    async def test_transaction_final_state_after_review(self, seeded_session, upload_with_rule):
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.types import Command

        upload_id = upload_with_rule
        workflow = create_workflow(seeded_session, checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": upload_id}}

        await workflow.ainvoke({"upload_id": upload_id}, config)

        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        sar_txn_ids = {sar.transaction_id for sar in sars}
        for sar in sars:
            sar.status = "confirmed"
            sar.reviewed_at = datetime.now(UTC).isoformat()
            sar.review_notes = "Reviewed"
        await seeded_session.commit()

        await workflow.ainvoke(Command(resume="all_reviewed"), config)

        upload = await seeded_session.get(UploadedFiles, upload_id)
        assert upload.status == "complete"

        upload_statuses = (await seeded_session.execute(
            select(UploadStatus).where(UploadStatus.upload_id == upload_id)
        )).scalars().all()
        status_sequence = [s.status for s in upload_statuses]
        assert "uploaded" in status_sequence
        assert "pending_human" in status_sequence
        assert "complete" in status_sequence
