from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.llm import LLMClient
from src.aml_workflow.nodes.runner import run_node
from src.aml_workflow.state import WorkflowState
from src.bff.logger import logger


async def enrich_node(state: WorkflowState, db: AsyncSession, llm: LLMClient | None, mode: str) -> dict:
    async def impl(state: WorkflowState) -> dict:
        from src.aml_workflow.enrichment import enrich_transactions

        flagged_ids = {r["transaction_id"] for r in state["results"] if r["status"] == "flagged"}
        flagged_txns = [{**t, "status": "flagged"} for t in state["transactions"] if t["id"] in flagged_ids]
        enriched = await enrich_transactions(db, flagged_txns, state["upload_id"])
        logger.info("Enriched %d customers for upload %s", len(enriched), state["upload_id"])
        return {"enriched_data": enriched}

    return await run_node(state, db, "enrich_node", impl)
