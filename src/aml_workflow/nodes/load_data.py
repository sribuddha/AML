from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.llm import LLMClient
from src.aml_workflow.nodes.runner import run_node
from src.aml_workflow.state import WorkflowState
from src.bff.logger import logger
from src.core.utils import now as _now


async def load_data_node(state: WorkflowState, db: AsyncSession, llm: LLMClient | None, mode: str) -> dict:
    async def impl(state: WorkflowState) -> dict:
        from src.core.models.rule import Rule
        from src.core.models.validation_result import ValidationResult
        from src.core.models.transaction import Transaction

        upload_id = state["upload_id"]

        already_validated = (
            select(ValidationResult.transaction_id)
            .where(ValidationResult.upload_id == upload_id)
            .scalar_subquery()
        )

        txn_stmt = select(Transaction).where(
            Transaction.upload_id == upload_id,
            Transaction.id.not_in(already_validated),
        )

        txn_rows = await db.execute(txn_stmt)
        transactions = []
        for t in txn_rows.scalars().all():
            transactions.append({
                "id": t.id,
                "account_id": t.account_id,
                "customer_id": t.customer_id,
                "amount": t.amount,
                "counterparty": t.counterparty,
                "city": t.city,
                "state": t.state,
                "country": t.country,
                "date": t.date,
                "source_txn_id": t.source_txn_id,
            })

        rule_rows = await db.execute(
            select(Rule).where(Rule.status == "active", Rule.type == "deterministic")
        )
        rules = [
            {"id": r.id, "name": r.name, "rules_json": r.rules_json, "severity": r.severity or "medium"}
            for r in rule_rows.scalars().all()
        ]

        logger.info("Loaded %d transactions and %d rules for upload %s", len(transactions), len(rules), upload_id)

        return {
            "transactions": transactions,
            "rules": rules,
            "validated_at": _now(),
            "triage_results": {},
            "enriched_data": {},
            "sars": [],
        }

    return await run_node(state, db, "load_data", impl)
