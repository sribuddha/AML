"""Eval-style triage scenario tests.

Each test documents a real-world triage path through the graph
with assertions on both state output and DB side effects.
"""

from datetime import datetime, UTC
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from src.aml_workflow.graph import create_workflow
from src.aml_workflow.llm import TriageDecision, SarResult
from src.aml_workflow.models.enrichment_snapshot import EnrichmentSnapshot
from src.aml_workflow.models.rule import Rule
from src.aml_workflow.models.sar import SAR
from src.aml_workflow.models.validation_result import ValidationResult
from src.file_processor.models import Transaction, UploadedFiles


def _make_batch_triage(td: TriageDecision):
    async def batch_fn(*args, **kwargs):
        txns = args[1] if len(args) > 1 else kwargs.get("transactions", [])
        return [td for _ in txns]
    return batch_fn


def _make_batch_sar(sr: SarResult):
    async def batch_fn(*args, **kwargs):
        txns = args[1] if len(args) > 1 else kwargs.get("transactions", [])
        return [sr for _ in txns]
    return batch_fn


@pytest.fixture
def mock_llm_escalate():
    m = AsyncMock()
    m.triage_batch.side_effect = _make_batch_triage(TriageDecision(escalate=True, reason="High value offshore", confidence=0.9))
    m.triage_stage3_batch.side_effect = _make_batch_triage(TriageDecision(escalate=True, reason="Deep-dive confirms risk", confidence=0.85))
    m.generate_sar_batch.side_effect = _make_batch_sar(SarResult(content="Suspicious Activity Report body text", raw_response='{"sar": "test"}'))
    return m


@pytest.fixture
def mock_llm_clear():
    m = AsyncMock()
    m.triage_batch.side_effect = _make_batch_triage(TriageDecision(escalate=False, reason="Routine amount", confidence=0.6))
    m.triage_stage3_batch.side_effect = _make_batch_triage(TriageDecision(escalate=False, reason="No pattern found", confidence=0.3))
    m.generate_sar_batch.side_effect = _make_batch_sar(SarResult(content="Suspicious Activity Report body text", raw_response='{"sar": "test"}'))
    return m


@pytest.fixture
def mock_llm_stage3_clear():
    """Stage 2 escalates, Stage 3 reverses."""
    m = AsyncMock()
    m.triage_batch.side_effect = _make_batch_triage(TriageDecision(escalate=True, reason="High value offshore", confidence=0.9))
    m.triage_stage3_batch.side_effect = _make_batch_triage(TriageDecision(escalate=False, reason="Deep-dive found no pattern", confidence=0.3))
    m.generate_sar_batch.side_effect = _make_batch_sar(SarResult(content="Suspicious Activity Report body text", raw_response='{"sar": "test"}'))
    return m


async def _seed_upload_with_rule(session) -> str:
    upload_id = "eval-upload-1"
    now = datetime.now(UTC).isoformat()
    upload = UploadedFiles(
        id=upload_id, filename="eval.csv", status="completed",
        total_rows=2, accepted_count=2, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    session.add(upload)

    session.add(Transaction(
        id="eval-txn-1", upload_id=upload_id,
        account_id="ACC001", customer_id="CUST001",
        amount=100000.00, counterparty="Offshore Ltd",
        country="Cayman Islands", date="2026-06-01",
        source_txn_id="TXN100", created_at=now, updated_at=now,
    ))
    session.add(Transaction(
        id="eval-txn-2", upload_id=upload_id,
        account_id="ACC003", customer_id="CUST002",
        amount=500.00, counterparty="Local Shop",
        city="Boston", state="MA", country="US", date="2026-06-02",
        source_txn_id="TXN101", created_at=now, updated_at=now,
    ))

    session.add(Rule(
        id="eval-rule-1", name="High Value Check",
        type="deterministic", status="active",
        rules_json='[{"field": "amount", "operator": ">", "value": 10000}]',
        created_at=now, updated_at=now,
    ))
    await session.commit()
    return upload_id


# ── Stage 2 scenarios ────────────────────────────────────────────


class TestStage2Scenarios:
    """Stage 2: LLM triage decides, placeholder SAR."""

    async def test_flagged_txn_escalates_to_high_risk(self, seeded_session, mock_llm_escalate):
        upload_id = await _seed_upload_with_rule(seeded_session)
        workflow = create_workflow(seeded_session, mock_llm_escalate, mode="stage2")
        state = await workflow.ainvoke({"upload_id": upload_id})

        txn1 = state["triage_results"]["eval-txn-1"]
        assert txn1["risk_level"] == "high"
        assert "High value" in txn1["triage_reasoning"]

        vrs = (await seeded_session.execute(
            select(ValidationResult).where(ValidationResult.upload_id == upload_id)
        )).scalars().all()
        for vr in vrs:
            if vr.transaction_id == "eval-txn-1":
                assert vr.risk_level == "high"
                assert vr.triage_reasoning is not None
                break

        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        assert len(sars) == 1

    async def test_flagged_txn_auto_reviewed(self, seeded_session, mock_llm_clear):
        upload_id = await _seed_upload_with_rule(seeded_session)
        workflow = create_workflow(seeded_session, mock_llm_clear, mode="stage2")
        state = await workflow.ainvoke({"upload_id": upload_id})

        txn1 = state["triage_results"]["eval-txn-1"]
        assert txn1["risk_level"] == "auto_reviewed"
        assert "Routine amount" in txn1["triage_reasoning"]

        vrs = (await seeded_session.execute(
            select(ValidationResult).where(ValidationResult.upload_id == upload_id)
        )).scalars().all()
        for vr in vrs:
            if vr.transaction_id == "eval-txn-1":
                assert vr.risk_level == "auto_reviewed"
                break

        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        assert len(sars) == 0

    async def test_enrichment_runs_before_stage2(self, seeded_session, mock_llm_escalate):
        upload_id = await _seed_upload_with_rule(seeded_session)
        workflow = create_workflow(seeded_session, mock_llm_escalate, mode="stage2")
        state = await workflow.ainvoke({"upload_id": upload_id})

        assert "enriched_data" in state
        enriched = state["enriched_data"]
        assert "CUST001" in enriched
        assert enriched["CUST001"]["customer_txn_count_30d"] == 1

        snaps = (await seeded_session.execute(
            select(EnrichmentSnapshot).where(EnrichmentSnapshot.upload_id == upload_id)
        )).scalars().all()
        assert len(snaps) == 1
        assert snaps[0].customer_id == "CUST001"


# ── Stage 3 scenarios ────────────────────────────────────────────


class TestStage3Scenarios:
    """Stage 3: deep-dive can confirm or reverse Stage 2."""

    async def test_stage3_confirms_escalation(self, seeded_session, mock_llm_escalate):
        upload_id = await _seed_upload_with_rule(seeded_session)
        workflow = create_workflow(seeded_session, mock_llm_escalate, mode="full")
        state = await workflow.ainvoke({"upload_id": upload_id})

        txn1 = state["triage_results"]["eval-txn-1"]
        assert txn1["risk_level"] == "high"

        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        assert len(sars) == 1
        assert sars[0].content == "Suspicious Activity Report body text"

    async def test_stage3_reverses_escalation(self, seeded_session, mock_llm_stage3_clear):
        upload_id = await _seed_upload_with_rule(seeded_session)
        workflow = create_workflow(seeded_session, mock_llm_stage3_clear, mode="full")
        state = await workflow.ainvoke({"upload_id": upload_id})

        txn1 = state["triage_results"]["eval-txn-1"]
        assert txn1["risk_level"] == "auto_reviewed"
        assert "Deep-dive found no pattern" in txn1["triage_reasoning"]

        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        assert len(sars) == 0

    async def test_stage3_skipped_when_none_escalated(self, seeded_session, mock_llm_clear):
        upload_id = await _seed_upload_with_rule(seeded_session)
        workflow = create_workflow(seeded_session, mock_llm_clear, mode="full")
        state = await workflow.ainvoke({"upload_id": upload_id})

        assert not mock_llm_clear.triage_stage3_batch.called
        for txn_id, result in state["triage_results"].items():
            assert result["risk_level"] == "auto_reviewed"

        sars = (await seeded_session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )).scalars().all()
        assert len(sars) == 0

    async def test_stage3_enrichment_available_in_context(self, seeded_session, mock_llm_escalate):
        upload_id = await _seed_upload_with_rule(seeded_session)
        workflow = create_workflow(seeded_session, mock_llm_escalate, mode="full")
        await workflow.ainvoke({"upload_id": upload_id})

        args, kwargs = mock_llm_escalate.triage_batch.call_args
        enriched_list = kwargs.get("enriched_context_list")
        assert enriched_list is not None
        assert len(enriched_list) > 0
        assert enriched_list[0]["customer_txn_count_30d"] == 1
