from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from langgraph.errors import GraphInterrupt
from langgraph.types import interrupt

from src.aml_workflow.llm import LLMClient
from src.aml_workflow.nodes.runner import run_node
from src.aml_workflow.services import _set_upload_status, record_transaction_status
from src.aml_workflow.state import WorkflowState
from src.bff.logger import logger
from src.core.utils import now as _now


PLACEHOLDER_SAR = "Auto-flagged for human review"


async def sar_node(state: WorkflowState, db: AsyncSession, llm: LLMClient | None, mode: str) -> dict:
    async def impl(state: WorkflowState) -> dict:
        from src.core.models.sar import SAR

        now = _now()
        sars: list[dict] = []

        llm_batch: list[tuple[dict, dict, dict]] = []
        placeholder_items: list[tuple[dict, dict, dict]] = []

        for result in state["results"]:
            if result.get("risk_level") != "high":
                continue

            txn_id = result["transaction_id"]
            txn = next((t for t in state["transactions"] if t["id"] == txn_id), None)
            if txn is None:
                continue

            flag_details = result.get("flag_details") or {}

            if mode in ("stage3", "full"):
                from src.aml_workflow.llm import TriageDecision
                triage = TriageDecision(
                    escalate=True,
                    reason=result.get("triage_reasoning", ""),
                    confidence=result.get("llm_confidence", 0.0),
                )
                llm_batch.append((result, txn, flag_details, triage))
            else:
                placeholder_items.append((result, txn, flag_details))

        if llm_batch:
            results_list, txns_list, flags_list, triage_list = zip(*llm_batch)
            sar_results = await llm.generate_sar_batch(list(txns_list), list(flags_list), list(triage_list))
            for (result, txn, _, _), sar_result in zip(llm_batch, sar_results):
                rule_id = next(iter((result.get("flag_details") or {}).keys()), None)
                sars.append({
                    "transaction_id": result["transaction_id"],
                    "upload_id": state["upload_id"],
                    "rule_id": rule_id,
                    "content": sar_result.content,
                    "raw_llm_response": sar_result.raw_response,
                    "llm_confidence": result.get("llm_confidence"),
                    "triage_reasoning": result.get("triage_reasoning"),
                    "triage_stage": result.get("triage_stage"),
                    "status": "pending_review",
                    "created_at": now,
                    "updated_at": now,
                })

        for result, txn, flag_details in placeholder_items:
            rule_id = next(iter(flag_details.keys()), None) if flag_details else None
            sars.append({
                "transaction_id": result["transaction_id"],
                "upload_id": state["upload_id"],
                "rule_id": rule_id,
                "content": PLACEHOLDER_SAR,
                "raw_llm_response": None,
                "llm_confidence": result.get("llm_confidence"),
                "triage_reasoning": result.get("triage_reasoning"),
                "triage_stage": result.get("triage_stage"),
                "status": "pending_review",
                "created_at": now,
                "updated_at": now,
            })

        if sars:
            objs = [SAR(**s) for s in sars]
            db.add_all(objs)
            await db.flush()

            for sar_obj in objs:
                await record_transaction_status(db, sar_obj.transaction_id, "pending_review")

            await _set_upload_status(db, state["upload_id"], "pending_human")

            await db.commit()
            logger.info("Created %d SARs for upload %s", len(sars), state["upload_id"])

        return {"sars": sars}

    return await run_node(state, db, "sar_node", impl)


async def human_review_node(state: WorkflowState, db: AsyncSession, llm: LLMClient | None, mode: str) -> dict:
    async def impl(state: WorkflowState) -> dict:
        sars = state.get("sars", [])
        if not sars:
            return {"human_review_complete": True}

        from src.core.models.sar import SAR
        from src.bff.database import async_session_factory

        async with async_session_factory() as fresh_db:
            pending = (
                await fresh_db.execute(
                    select(func.count()).select_from(SAR).where(
                        SAR.upload_id == state["upload_id"],
                        SAR.status == "pending_review",
                    )
                )
            ).scalar() or 0

        if pending > 0:
            interrupt({
                "message": "SARs pending human review",
                "upload_id": state["upload_id"],
                "pending_count": pending,
            })

        return {"human_review_complete": True}

    return await run_node(state, db, "human_review", impl)


async def finalize_node(state: WorkflowState, db: AsyncSession, llm: LLMClient | None, mode: str) -> dict:
    async def impl(state: WorkflowState) -> dict:
        upload_id = state["upload_id"]

        human_reviewed = state.get("human_review_complete", False)
        has_sars = bool(state.get("sars"))

        final_status = "pending_human" if (has_sars and not human_reviewed) else "complete"
        await _set_upload_status(db, upload_id, final_status)
        await db.commit()

        logger.info("Upload %s status: %s", upload_id, final_status)
        return {}

    return await run_node(state, db, "finalize", impl)
