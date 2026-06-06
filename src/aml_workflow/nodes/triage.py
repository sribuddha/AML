from __future__ import annotations

from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.llm import LLMClient
from src.aml_workflow.nodes.runner import run_node
from src.aml_workflow.services import record_transaction_status
from src.aml_workflow.state import WorkflowState
from src.bff.config import get_velocity_zscore_threshold, get_structuring_24h_threshold
from src.bff.logger import logger
from src.core.utils import now as _now


async def stage2_triage_node(state: WorkflowState, db: AsyncSession, llm: LLMClient | None, mode: str) -> dict:
    async def impl(state: WorkflowState) -> dict:
        from src.core.models.transaction import Transaction as TxnModel
        from src.core.models.validation_result import ValidationResult

        flagged = [r for r in state["results"] if r["status"] == "flagged"]
        now = _now()

        llm_batch: list[tuple[dict, dict, dict, dict | None]] = []
        bypasses: list[tuple[dict, dict]] = []
        hard_bypasses: list[tuple[dict, dict]] = []

        for result in flagged:
            txn_id = result["transaction_id"]
            txn = next((t for t in state["transactions"] if t["id"] == txn_id), None)
            if txn is None:
                continue

            if result.get("hard_escalate"):
                hard_bypasses.append((result, txn))
            elif mode == "stage1":
                bypasses.append((result, txn))
            else:
                flag_details = result.get("flag_details") or {}
                enriched = state.get("enriched_data", {})
                customer_id = txn.get("customer_id", "")
                enriched_context = enriched.get(customer_id) if enriched else None
                llm_batch.append((result, txn, flag_details, enriched_context))

        if llm_batch:
            results_list, txns_list, flags_list, enrichments_list = zip(*llm_batch)
            decisions = await llm.triage_batch(list(txns_list), list(flags_list), rules=state["rules"], enriched_context_list=list(enrichments_list))
            for (result, txn, _, _), decision in zip(llm_batch, decisions):
                if decision.escalate:
                    result["risk_level"] = "high"
                else:
                    result["risk_level"] = "auto_reviewed"
                result["triage_reasoning"] = decision.reason
                result["llm_confidence"] = decision.confidence
                result["triage_stage"] = "stage2"

                new_status = "escalated" if decision.escalate else "clean"
                await record_transaction_status(db, result["transaction_id"], new_status)

                await db.execute(
                    sa_update(ValidationResult)
                    .where(ValidationResult.transaction_id == result["transaction_id"], ValidationResult.upload_id == state["upload_id"])
                    .values(risk_level=result["risk_level"], triage_reasoning=decision.reason, raw_llm_response=decision.raw_response, updated_at=now)
                )

        for result, txn in hard_bypasses:
            from src.aml_workflow.llm import TriageDecision
            decision = TriageDecision(
                escalate=True,
                reason="Hard-escalated — high-risk pattern (structuring 24h threshold exceeded)",
                confidence=1.0,
            )
            result["risk_level"] = "high"
            result["triage_reasoning"] = decision.reason
            result["llm_confidence"] = decision.confidence
            result["triage_stage"] = "stage2"

            await record_transaction_status(db, result["transaction_id"], "escalated")

            await db.execute(
                sa_update(ValidationResult)
                .where(ValidationResult.transaction_id == result["transaction_id"], ValidationResult.upload_id == state["upload_id"])
                .values(risk_level="high", triage_reasoning=decision.reason, raw_llm_response=decision.raw_response, updated_at=now)
            )

        for result, txn in bypasses:
            from src.aml_workflow.llm import TriageDecision
            decision = TriageDecision(
                escalate=True,
                reason="Escalated to human review (Stage 1 mode)",
                confidence=0.5,
            )
            result["risk_level"] = "high"
            result["triage_reasoning"] = decision.reason
            result["llm_confidence"] = decision.confidence
            result["triage_stage"] = "stage2"

            await record_transaction_status(db, result["transaction_id"], "escalated")

            await db.execute(
                sa_update(ValidationResult)
                .where(ValidationResult.transaction_id == result["transaction_id"], ValidationResult.upload_id == state["upload_id"])
                .values(risk_level="high", triage_reasoning=decision.reason, raw_llm_response=decision.raw_response, updated_at=now)
            )

        await db.commit()

        escalated_count = sum(1 for r in flagged if r.get("risk_level") == "high")
        logger.info("Stage2 triage: %d escalated, %d auto-reviewed out of %d flagged",
                     escalated_count, len(flagged) - escalated_count, len(flagged))

        return {"triage_results": {r["transaction_id"]: r for r in flagged}}

    return await run_node(state, db, "stage2_triage", impl)


async def stage3_triage_node(state: WorkflowState, db: AsyncSession, llm: LLMClient | None, mode: str) -> dict:
    async def impl(state: WorkflowState) -> dict:
        from src.core.models.transaction import Transaction
        from src.core.models.validation_result import ValidationResult

        escalated = [r for r in state["results"] if r.get("risk_level") == "high"]
        if not escalated:
            return {}

        now = _now()

        llm_batch: list[tuple[dict, dict, dict, list[dict]]] = []
        bypasses: list[tuple[dict, dict]] = []

        # Collect unique customer IDs for batch recent_txns query
        customer_ids = set()
        for result in escalated:
            txn_id = result["transaction_id"]
            txn = next((t for t in state["transactions"] if t["id"] == txn_id), None)
            if txn is not None:
                customer_ids.add(txn["customer_id"])

        # Single DB query for all customers' recent transactions
        customer_recent: dict[str, list[dict]] = {}
        if customer_ids and mode in ("stage3", "full"):
            from sqlalchemy import select as sa_select
            recent_rows = (
                await db.execute(
                    sa_select(Transaction).where(
                        Transaction.customer_id.in_(list(customer_ids))
                    ).order_by(Transaction.customer_id, Transaction.date.desc())
                )
            ).scalars().all()

            for t in recent_rows:
                cid = t.customer_id
                entry = {"amount": t.amount, "counterparty": t.counterparty,
                         "city": t.city, "state": t.state, "country": t.country, "date": t.date}
                customer_recent.setdefault(cid, []).append(entry)

        for result in escalated:
            txn_id = result["transaction_id"]
            txn = next((t for t in state["transactions"] if t["id"] == txn_id), None)
            if txn is None:
                continue

            flag_details = result.get("flag_details") or {}

            if mode in ("stage3", "full"):
                # Filter out the current transaction from recent list
                recent_list = [
                    r for r in customer_recent.get(txn["customer_id"], [])
                    if r.get("date") != txn.get("date") or r.get("amount") != txn.get("amount")
                ][:20]
                llm_batch.append((result, txn, flag_details, recent_list))
            else:
                bypasses.append((result, txn))

        if llm_batch:
            results_list, txns_list, flags_list, recent_list = zip(*llm_batch)
            decisions = await llm.triage_stage3_batch(list(txns_list), list(flags_list), list(recent_list), rules=state["rules"])
            for (result, txn, _, _), decision in zip(llm_batch, decisions):
                new_status = "pending_review" if decision.escalate else "clean"
                risk_level = "high" if decision.escalate else "auto_reviewed"

                result["risk_level"] = risk_level
                result["triage_reasoning"] = decision.reason
                result["llm_confidence"] = decision.confidence
                result["triage_stage"] = "stage3"
                result["sar_content"] = decision.reason if decision.escalate else ""

                await record_transaction_status(db, result["transaction_id"], new_status)

                await db.execute(
                    sa_update(ValidationResult)
                    .where(ValidationResult.transaction_id == result["transaction_id"], ValidationResult.upload_id == state["upload_id"])
                    .values(risk_level=risk_level, triage_reasoning=decision.reason, raw_llm_response=decision.raw_response, updated_at=now)
                )

        for result, txn in bypasses:
            from src.aml_workflow.llm import TriageDecision
            decision = TriageDecision(
                escalate=True,
                reason="Escalated (mode bypasses stage3 analysis)",
                confidence=0.5,
            )
            result["risk_level"] = "high"
            result["triage_reasoning"] = decision.reason
            result["llm_confidence"] = decision.confidence
            result["triage_stage"] = "stage3"
            result["sar_content"] = decision.reason

            await record_transaction_status(db, result["transaction_id"], "pending_review")

            await db.execute(
                sa_update(ValidationResult)
                .where(ValidationResult.transaction_id == result["transaction_id"], ValidationResult.upload_id == state["upload_id"])
                .values(risk_level="high", triage_reasoning=decision.reason, raw_llm_response=decision.raw_response, updated_at=now)
            )

        await db.commit()

        pending_count = sum(1 for r in escalated if r.get("risk_level") == "high")
        logger.info("Stage3 triage: %d pending_review, %d cleared out of %d escalated",
                     pending_count, len(escalated) - pending_count, len(escalated))

        return {}

    return await run_node(state, db, "stage3_triage", impl)
