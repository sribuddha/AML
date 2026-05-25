import asyncio
import uuid
from datetime import datetime, UTC
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from src.aml_workflow.graph import create_workflow
from src.aml_workflow.llm import SarResult, TriageDecision
from src.aml_workflow.models.rule import Rule
from src.aml_workflow.models.validation_result import ValidationResult
from src.file_processor.models import Transaction, UploadedFiles


@pytest.fixture
def mock_llm():
    m = AsyncMock()
    m.triage_batch.return_value = [TriageDecision(escalate=True, reason="High value offshore", confidence=0.9)]
    m.triage_stage3_batch.return_value = [TriageDecision(escalate=True, reason="Deep-dive confirms risk", confidence=0.85)]
    m.generate_sar_batch.return_value = [SarResult(content="Suspicious Activity Report body text", raw_response='{"sar": "test"}')]
    return m


@pytest.fixture
def mock_llm_no_escalate():
    m = AsyncMock()
    m.triage_batch.return_value = [TriageDecision(escalate=False, reason="Routine amount", confidence=0.6)]
    m.triage_stage3_batch.return_value = [TriageDecision(escalate=False, reason="No pattern found", confidence=0.3)]
    m.generate_sar_batch.return_value = [SarResult(content="Suspicious Activity Report body text", raw_response='{"sar": "test"}')]
    return m


@pytest.fixture
def mock_llm_escalate_then_clear():
    """Stage 2 escalates, but Stage 3 reverses (deep-dive clears the alert)."""
    m = AsyncMock()
    m.triage_batch.return_value = [TriageDecision(escalate=True, reason="High value offshore", confidence=0.9)]
    m.triage_stage3_batch.return_value = [TriageDecision(escalate=False, reason="Deep-dive found no pattern", confidence=0.3)]
    m.generate_sar_batch.return_value = [SarResult(content="Suspicious Activity Report body text", raw_response='{"sar": "test"}')]
    return m


@pytest.fixture
def upload_id():
    return str(uuid.uuid4())


@pytest.fixture
async def seeded_upload(seeded_session, upload_id):
    now = datetime.now(UTC).isoformat()
    upload = UploadedFiles(
        id=upload_id, filename="test.csv", status="completed",
        total_rows=2, accepted_count=2, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)

    txns = [
        Transaction(
            id=str(uuid.uuid4()), upload_id=upload_id,
            account_id="ACC001", customer_id="CUST001",
            amount=100000.00, counterparty="Offshore Ltd",
            country="Cayman Islands", date="2026-06-01",
            source_txn_id="TXN100", created_at=now, updated_at=now,
        ),
        Transaction(
            id=str(uuid.uuid4()), upload_id=upload_id,
            account_id="ACC003", customer_id="CUST002",
            amount=500.00, counterparty="Local Shop",
            country="US", date="2026-06-02",
            source_txn_id="TXN101", created_at=now, updated_at=now,
        ),
    ]
    seeded_session.add_all(txns)

    rule = Rule(
        id=str(uuid.uuid4()), name="High Value Check",
        type="deterministic", status="active",
        rules_json='[{"field": "amount", "operator": ">", "value": 10000}]',
        created_at=now, updated_at=now,
    )
    seeded_session.add(rule)
    await seeded_session.commit()
    return upload_id, txns, rule


class TestLoadData:
    async def test_loads_transactions_and_rules(self, seeded_session, seeded_upload):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session)
        state = await workflow.ainvoke({"upload_id": upload_id})
        assert len(state["transactions"]) == 2
        assert len(state["rules"]) == 1
        assert state["rules"][0]["name"] == "High Value Check"
        assert "upload_id" in state

    async def test_skips_already_validated(self, seeded_session, seeded_upload):
        upload_id, txns, _ = seeded_upload
        now = datetime.now(UTC).isoformat()
        seeded_session.add(ValidationResult(
            upload_id=upload_id,
            transaction_id=txns[0].id,
            status="flagged",
            validated_at=now,
            created_at=now, updated_at=now,
        ))
        await seeded_session.commit()
        workflow = create_workflow(seeded_session)
        state = await workflow.ainvoke({"upload_id": upload_id})
        assert len(state["transactions"]) == 1
        assert state["transactions"][0]["id"] == txns[1].id


class TestStatusTransitions:
    async def test_upload_status_flows_through(self, seeded_session, seeded_upload):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session)
        await workflow.ainvoke({"upload_id": upload_id})
        upload = await seeded_session.get(UploadedFiles, upload_id)
        assert upload is not None
        assert upload.status in ("processing", "pending_human", "complete")


class TestTriageNode:
    async def test_calls_llm_on_flagged(self, seeded_session, seeded_upload, mock_llm):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm)
        state = await workflow.ainvoke({"upload_id": upload_id})
        assert mock_llm.triage_batch.called
        triage_results = state["triage_results"]
        assert len(triage_results) > 0
        for txn_id, result in triage_results.items():
            assert isinstance(result, dict)
            assert "risk_level" in result
            assert "triage_reasoning" in result

    async def test_skips_llm_when_no_flag(self, seeded_session, upload_id, mock_llm):
        now = datetime.now(UTC).isoformat()
        upload = UploadedFiles(
            id=upload_id, filename="clean.csv", status="completed",
            total_rows=1, accepted_count=1, failed_count=0,
            uploaded_at=now, created_at=now, updated_at=now,
        )
        seeded_session.add(upload)
        txn = Transaction(
            id=str(uuid.uuid4()), upload_id=upload_id,
            account_id="ACC001", customer_id="CUST001",
            amount=50.00, counterparty="Local", city="New York", state="NY", country="US",
            date="2026-06-01", source_txn_id="TXN200",
            created_at=now, updated_at=now, 
        )
        seeded_session.add(txn)
        await seeded_session.commit()
        workflow = create_workflow(seeded_session, mock_llm)
        state = await workflow.ainvoke({"upload_id": upload_id})
        assert not mock_llm.triage_batch.called
        assert state["triage_results"] == {}


class TestWriteResults:
    async def test_writes_validation_results(self, seeded_session, seeded_upload):
        upload_id, txns, rule = seeded_upload
        workflow = create_workflow(seeded_session)
        await workflow.ainvoke({"upload_id": upload_id})
        vrs = (await seeded_session.execute(
            select(ValidationResult).where(ValidationResult.upload_id == upload_id)
        )).scalars().all()
        assert len(vrs) == 2
        for vr in vrs:
            assert vr.status in ("clean", "flagged")
            assert vr.transaction_id in (txns[0].id, txns[1].id)

    async def test_flagged_result_has_triage_data(self, seeded_session, seeded_upload, mock_llm):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm)
        await workflow.ainvoke({"upload_id": upload_id})
        vrs = (await seeded_session.execute(
            select(ValidationResult).where(ValidationResult.upload_id == upload_id)
        )).scalars().all()
        flagged = [vr for vr in vrs if vr.status == "flagged"]
        for vr in flagged:
            assert vr.risk_level is not None
            assert vr.triage_reasoning is not None


class TestAuditLog:
    async def test_creates_entity_audit_log_entries(self, seeded_session, seeded_upload, mock_llm):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm)
        await workflow.ainvoke({"upload_id": upload_id})
        from src.aml_workflow.models.transaction_status import TransactionStatus
        from src.aml_workflow.models.upload_status import UploadStatus
        txn_statuses = (await seeded_session.execute(
            select(TransactionStatus).where(
                TransactionStatus.transaction_id.in_(
                    select(Transaction.id).where(Transaction.upload_id == upload_id)
                )
            )
        )).scalars().all()
        upload_statuses = (await seeded_session.execute(
            select(UploadStatus).where(UploadStatus.upload_id == upload_id)
        )).scalars().all()

        txn_status_set = {s.status for s in txn_statuses}
        assert "flagged" in txn_status_set
        assert "escalated" in txn_status_set
        assert "pending_review" in txn_status_set

        upload_status_set = {s.status for s in upload_statuses}
        assert "pending_human" in upload_status_set

        assert all(s.actor == "system" for s in txn_statuses)
        assert all(s.actor == "system" for s in upload_statuses)
        assert all(s.created_at is not None for s in txn_statuses)
        assert all(s.created_at is not None for s in upload_statuses)

    async def test_audit_log_includes_triage_data(self, seeded_session, seeded_upload, mock_llm):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm)
        await workflow.ainvoke({"upload_id": upload_id})
        from src.aml_workflow.models.transaction_status import TransactionStatus
        txn_statuses = (await seeded_session.execute(
            select(TransactionStatus).where(
                TransactionStatus.transaction_id.in_(
                    select(Transaction.id).where(Transaction.upload_id == upload_id)
                )
            )
        )).scalars().all()
        flagged_statuses = [s for s in txn_statuses if s.status == "flagged"]
        assert len(flagged_statuses) >= 1


class TestSarNode:
    async def test_inserts_sar_when_escalated(self, seeded_session, seeded_upload, mock_llm):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm)
        await workflow.ainvoke({"upload_id": upload_id})
        from src.aml_workflow.models.sar import SAR
        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        assert len(sars) > 0
        for sar in sars:
            assert sar.content == "Suspicious Activity Report body text"
            assert sar.status == "pending_review"

    async def test_no_sar_when_not_escalated(self, seeded_session, upload_id, mock_llm_no_escalate):
        now = datetime.now(UTC).isoformat()
        upload = UploadedFiles(
            id=upload_id, filename="flagged.csv", status="completed",
            total_rows=1, accepted_count=1, failed_count=0,
            uploaded_at=now, created_at=now, updated_at=now,
        )
        seeded_session.add(upload)
        rule = Rule(
            id=str(uuid.uuid4()), name="High Value Check",
            type="deterministic", status="active",
            rules_json='[{"field": "amount", "operator": ">", "value": 100}]',
            created_at=now, updated_at=now,
        )
        seeded_session.add(rule)
        txn = Transaction(
            id=str(uuid.uuid4()), upload_id=upload_id,
            account_id="ACC001", customer_id="CUST001",
            amount=500.00, counterparty="Local", city="New York", state="NY", country="US",
            date="2026-06-01", source_txn_id="TXN300",
            created_at=now, updated_at=now, 
        )
        seeded_session.add(txn)
        await seeded_session.commit()
        workflow = create_workflow(seeded_session, mock_llm_no_escalate)
        await workflow.ainvoke({"upload_id": upload_id})
        from src.aml_workflow.models.sar import SAR
        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        assert len(sars) == 0


class TestFinalize:
    async def test_complete_when_no_sars(self, seeded_session, upload_id):
        now = datetime.now(UTC).isoformat()
        upload = UploadedFiles(
            id=upload_id, filename="clean.csv", status="completed",
            total_rows=1, accepted_count=1, failed_count=0,
            uploaded_at=now, created_at=now, updated_at=now,
        )
        seeded_session.add(upload)
        txn = Transaction(
            id=str(uuid.uuid4()), upload_id=upload_id,
            account_id="ACC001", customer_id="CUST001",
            amount=50.00, counterparty="Local", city="New York", state="NY", country="US",
            date="2026-06-01", source_txn_id="TXN400",
            created_at=now, updated_at=now, 
        )
        seeded_session.add(txn)
        await seeded_session.commit()
        workflow = create_workflow(seeded_session)
        await workflow.ainvoke({"upload_id": upload_id})
        upload = await seeded_session.get(UploadedFiles, upload_id)
        assert upload.status == "complete"


# ── Mode tests ─────────────────────────────────────────────────────────


class TestEnrichNode:
    """Enrich_node integration: runs for flagged txns, populates state, feeds LLM."""

    async def test_enriched_data_populated_for_flagged(self, seeded_session, seeded_upload, mock_llm):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm, mode="stage2")
        state = await workflow.ainvoke({"upload_id": upload_id})
        enriched = state.get("enriched_data", {})
        assert len(enriched) == 1
        assert "CUST001" in enriched
        ctx = enriched["CUST001"]
        assert ctx["customer_txn_count_30d"] == 1
        assert ctx["customer_sum_30d"] == 100000.0
        assert ctx["structuring_24h_count"] == 0

    async def test_enriched_context_passed_to_llm_triage(self, seeded_session, seeded_upload, mock_llm):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm, mode="stage2")
        await workflow.ainvoke({"upload_id": upload_id})
        assert mock_llm.triage_batch.called
        args, kwargs = mock_llm.triage_batch.call_args
        enriched_list = kwargs.get("enriched_context_list")
        assert enriched_list is not None
        assert len(enriched_list) > 0
        assert enriched_list[0]["customer_txn_count_30d"] == 1
        assert enriched_list[0]["customer_sum_30d"] == 100000.0

    async def test_enriched_data_empty_when_no_flagged(self, seeded_session, upload_id, mock_llm):
        now = datetime.now(UTC).isoformat()
        upload = UploadedFiles(
            id=upload_id, filename="clean.csv", status="completed",
            total_rows=1, accepted_count=1, failed_count=0,
            uploaded_at=now, created_at=now, updated_at=now,
        )
        seeded_session.add(upload)
        txn = Transaction(
            id=str(uuid.uuid4()), upload_id=upload_id,
            account_id="ACC001", customer_id="CUST001",
            amount=50.00, counterparty="Local", city="New York", state="NY", country="US",
            date="2026-06-01", source_txn_id="TXN200",
            created_at=now, updated_at=now, 
        )
        seeded_session.add(txn)
        await seeded_session.commit()
        workflow = create_workflow(seeded_session, mock_llm, mode="stage2")
        state = await workflow.ainvoke({"upload_id": upload_id})
        assert state.get("enriched_data") == {}

    async def test_enrich_node_skipped_when_no_rules(self, seeded_session, upload_id, mock_llm):
        now = datetime.now(UTC).isoformat()
        upload = UploadedFiles(
            id=upload_id, filename="flagged_no_rules.csv", status="completed",
            total_rows=1, accepted_count=1, failed_count=0,
            uploaded_at=now, created_at=now, updated_at=now,
        )
        seeded_session.add(upload)
        txn = Transaction(
            id=str(uuid.uuid4()), upload_id=upload_id,
            account_id="ACC001", customer_id="CUST001",
            amount=100000.00, counterparty="Offshore Ltd",
            country="Cayman Islands", date="2026-06-01",
            source_txn_id="TXN300", created_at=now, updated_at=now,
        )
        seeded_session.add(txn)
        await seeded_session.commit()
        workflow = create_workflow(seeded_session, mock_llm, mode="stage2")
        state = await workflow.ainvoke({"upload_id": upload_id})
        assert not mock_llm.triage_batch.called
        assert state.get("enriched_data") == {}


class TestStage1Mode:
    """Stage 1: no LLM, all flagged → high risk, placeholder SAR."""

    async def test_triage_skips_llm_and_marks_all_high(self, seeded_session, seeded_upload, mock_llm):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm, mode="stage1")
        state = await workflow.ainvoke({"upload_id": upload_id})
        assert not mock_llm.triage_batch.called
        for txn_id, result in state["triage_results"].items():
            assert result["risk_level"] == "high"
            assert result["triage_reasoning"] is not None

    async def test_sar_writes_placeholder(self, seeded_session, seeded_upload, mock_llm):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm, mode="stage1")
        await workflow.ainvoke({"upload_id": upload_id})
        from src.aml_workflow.models.sar import SAR
        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        assert len(sars) > 0
        for sar in sars:
            assert "Auto-flagged" in sar.content
            assert mock_llm.generate_sar.call_count == 0


class TestStage2Mode:
    """Stage 2: LLM triage decides escalate, placeholder SAR."""

    async def test_triage_calls_llm(self, seeded_session, seeded_upload, mock_llm):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm, mode="stage2")
        await workflow.ainvoke({"upload_id": upload_id})
        assert mock_llm.triage_batch.called
        triage_data = list(mock_llm.triage_batch.call_args)
        assert triage_data is not None

    async def test_sar_uses_placeholder_despite_mock_content(self, seeded_session, seeded_upload, mock_llm):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm, mode="stage2")
        await workflow.ainvoke({"upload_id": upload_id})
        from src.aml_workflow.models.sar import SAR
        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        assert len(sars) > 0
        for sar in sars:
            assert "Auto-flagged" in sar.content
        assert mock_llm.generate_sar.call_count == 0

    async def test_non_escalated_risk_level(self, seeded_session, seeded_upload, mock_llm_no_escalate):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm_no_escalate, mode="stage2")
        state = await workflow.ainvoke({"upload_id": upload_id})
        triage_data = state["triage_results"]
        for txn_id, result in triage_data.items():
            assert result["risk_level"] == "auto_reviewed"


class TestFullMode:
    """Full: LLM triage + LLM SAR."""

    async def test_sar_uses_llm_content(self, seeded_session, seeded_upload, mock_llm):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm, mode="full")
        await workflow.ainvoke({"upload_id": upload_id})
        from src.aml_workflow.models.sar import SAR
        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        assert len(sars) > 0
        for sar in sars:
            assert sar.content == "Suspicious Activity Report body text"
        assert mock_llm.generate_sar_batch.called


class TestStage3Mode:
    """Stage 3: deep-dive analysis can reverse Stage 2 escalation."""

    async def test_stage3_reverses_escalation(self, seeded_session, seeded_upload, mock_llm_escalate_then_clear):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm_escalate_then_clear, mode="full")
        state = await workflow.ainvoke({"upload_id": upload_id})
        # Stage 2 escalates (high), Stage 3 reverses (auto_reviewed)
        for txn_id, result in state["triage_results"].items():
            assert result["risk_level"] == "auto_reviewed"
        assert mock_llm_escalate_then_clear.triage_batch.called
        assert mock_llm_escalate_then_clear.triage_stage3_batch.called

    async def test_stage3_no_sar_when_cleared(self, seeded_session, seeded_upload, mock_llm_escalate_then_clear):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm_escalate_then_clear, mode="full")
        await workflow.ainvoke({"upload_id": upload_id})
        from src.aml_workflow.models.sar import SAR
        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        assert len(sars) == 0
        assert mock_llm_escalate_then_clear.generate_sar.call_count == 0

    async def test_stage3_no_reversal_when_not_escalated(self, seeded_session, seeded_upload, mock_llm_no_escalate):
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm_no_escalate, mode="full")
        state = await workflow.ainvoke({"upload_id": upload_id})
        # Stage 2 does not escalate, so Stage 3 is skipped entirely
        assert not mock_llm_no_escalate.triage_stage3_batch.called
        for txn_id, result in state["triage_results"].items():
            assert result["risk_level"] == "auto_reviewed"


# ── Interrupt / Human-in-the-Loop tests ──────────────────────────


class TestHumanReviewInterrupt:
    """Tests for the interrupt() + checkpointer human-in-the-loop feature."""

    async def test_interrupts_when_sars_pending(self, seeded_session, seeded_upload, mock_llm):
        from langgraph.checkpoint.memory import MemorySaver
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm, checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": upload_id}}
        result = await workflow.ainvoke({"upload_id": upload_id}, config)
        assert "__interrupt__" in result, "Graph should interrupt when SARs are pending"

    async def test_resume_after_all_sars_reviewed(self, seeded_session, seeded_upload, mock_llm):
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.types import Command
        from src.aml_workflow.models.sar import SAR
        from sqlalchemy import select

        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm, checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": upload_id}}

        # First run — interrupts at human_review
        result = await workflow.ainvoke({"upload_id": upload_id}, config)
        assert "__interrupt__" in result

        # Simulate human reviewing all SARs via DB
        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        assert len(sars) > 0
        for sar in sars:
            sar.status = "approved"
            sar.review_notes = "Reviewed"
            sar.reviewed_at = datetime.now(UTC).isoformat()
        await seeded_session.commit()

        # Resume the graph
        final = await workflow.ainvoke(Command(resume="all_reviewed"), config)
        assert "__interrupt__" not in final
        assert final.get("human_review_complete") is True

        # Verify upload is now complete
        upload = await seeded_session.get(UploadedFiles, upload_id)
        assert upload.status == "complete"

    async def test_skips_interrupt_when_no_sars(self, seeded_session, upload_id):
        from langgraph.checkpoint.memory import MemorySaver
        from datetime import datetime, UTC

        now = datetime.now(UTC).isoformat()
        upload = UploadedFiles(
            id=upload_id, filename="clean.csv", status="completed",
            total_rows=1, accepted_count=1, failed_count=0,
            uploaded_at=now, created_at=now, updated_at=now,
        )
        seeded_session.add(upload)
        txn = Transaction(
            id=str(uuid.uuid4()), upload_id=upload_id,
            account_id="ACC001", customer_id="CUST001",
            amount=50.00, counterparty="Local", city="New York", state="NY", country="US",
            date="2026-06-01", source_txn_id="TXN400",
            created_at=now, updated_at=now, 
        )
        seeded_session.add(txn)
        await seeded_session.commit()

        workflow = create_workflow(seeded_session, checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": upload_id}}
        result = await workflow.ainvoke({"upload_id": upload_id}, config)
        assert "__interrupt__" not in result, "No interrupt expected when no SARs"

    async def test_sar_node_sets_pending_human(self, seeded_session, seeded_upload, mock_llm):
        from langgraph.checkpoint.memory import MemorySaver
        upload_id, _, _ = seeded_upload
        workflow = create_workflow(seeded_session, mock_llm, checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": upload_id}}
        await workflow.ainvoke({"upload_id": upload_id}, config)
        upload = await seeded_session.get(UploadedFiles, upload_id)
        assert upload.status == "pending_human"


class TestNodeRetryFailure:
    """_run_node retry/error handling: permanent failure propagates."""

    async def test_permanent_failure_no_retry_and_propagates(self, seeded_session, seeded_upload, mock_llm):
        from src.aml_workflow.triggers import run_validation
        upload_id, _, _ = seeded_upload
        mock_llm.triage_batch.side_effect = ValueError("LLM not available")
        with pytest.raises(ValueError, match="LLM not available"):
            await run_validation(upload_id, seeded_session, llm=mock_llm, mode="stage2")
        from src.file_processor.models import UploadedFiles
        upload = await seeded_session.get(UploadedFiles, upload_id)
        assert upload.status == "failed"

    async def test_retry_succeeded_after_transient_error(self, seeded_session, seeded_upload, mock_llm_no_escalate):
        upload_id, _, _ = seeded_upload
        call_count = 0

        async def triage_with_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("LLM timed out")
            return [TriageDecision(escalate=False, reason="Recovered", confidence=0.6)]

        mock_llm_no_escalate.triage_batch.side_effect = triage_with_retry
        workflow = create_workflow(seeded_session, mock_llm_no_escalate, mode="stage2")
        state = await workflow.ainvoke({"upload_id": upload_id})
        assert call_count == 2
        triage_results = state.get("triage_results", {})
        assert len(triage_results) > 0


class TestFailureEvents:
    """upload status events are recorded correctly."""

    async def test_workflow_failed_logs_audit_event(self, seeded_session, upload_id):
        from unittest.mock import patch

        with patch("src.aml_workflow.triggers.create_workflow") as mock:
            mock.return_value.ainvoke.side_effect = ValueError("Something went wrong")
            from src.aml_workflow.triggers import run_validation
            with pytest.raises(ValueError):
                await run_validation(upload_id, seeded_session)

        from src.aml_workflow.models.upload_status import UploadStatus
        statuses = (await seeded_session.execute(
            select(UploadStatus).where(
                UploadStatus.upload_id == upload_id,
                UploadStatus.status == "failed",
            )
        )).scalars().all()
        assert len(statuses) == 1

    async def test_workflow_started_and_completed_logged(self, seeded_session, upload_id):
        from src.aml_workflow.models.upload_status import UploadStatus

        now = datetime.now(UTC).isoformat()
        upload = UploadedFiles(
            id=upload_id, filename="clean.csv", status="completed",
            total_rows=1, accepted_count=1, failed_count=0,
            uploaded_at=now, created_at=now, updated_at=now,
        )
        seeded_session.add(upload)
        txn = Transaction(
            id=str(uuid.uuid4()), upload_id=upload_id,
            account_id="ACC001", customer_id="CUST001",
            amount=50.00, counterparty="Local", city="New York", state="NY", country="US",
            date="2026-06-01", source_txn_id="TXN400",
            created_at=now, updated_at=now, 
        )
        seeded_session.add(txn)
        await seeded_session.commit()

        from src.aml_workflow.triggers import run_validation
        await run_validation(upload_id, seeded_session)

        statuses = (await seeded_session.execute(
            select(UploadStatus)
            .where(UploadStatus.upload_id == upload_id)
            .order_by(UploadStatus.created_at)
        )).scalars().all()

        status_seq = [s.status for s in statuses]
        assert "processing" in status_seq
        assert "complete" in status_seq
        assert all(s.actor == "system" for s in statuses)

    async def test_is_transient_classification(self):
        from src.aml_workflow.graph import _is_transient

        assert _is_transient(asyncio.TimeoutError())
        assert _is_transient(TimeoutError())
        assert not _is_transient(ValueError("bad data"))
        assert not _is_transient(KeyError("missing"))
