from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, UTC, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.llm import LLMClient
from src.aml_workflow.nodes.runner import run_node
from src.aml_workflow.services import record_transaction_status
from src.aml_workflow.state import WorkflowState
from src.aml_workflow.validator import evaluate_rules
from src.bff.config import get_velocity_zscore_threshold, get_structuring_24h_threshold
from src.bff.logger import logger
from src.core.utils import now as _now


async def rule_engine_batch_node(state: WorkflowState, db: AsyncSession, llm: LLMClient | None, mode: str) -> dict:
    async def impl(state: WorkflowState) -> dict:
        from src.core.models.transaction import Transaction as TxnModel
        from src.core.models.validation_result import ValidationResult

        results: list[dict] = []
        validated_at = state["validated_at"]

        for txn in state["transactions"]:
            flag_details = evaluate_rules(txn, state["rules"])
            status = "flagged" if flag_details else "clean"
            results.append({
                "upload_id": state["upload_id"],
                "transaction_id": txn["id"],
                "status": status,
                "flag_details": flag_details if flag_details else None,
                "validated_at": validated_at,
                "created_at": validated_at,
                "updated_at": validated_at,
            })

        flagged_count = sum(1 for r in results if r["status"] == "flagged")
        logger.info("Rule engine (pre-velocity): %d flagged, %d clean out of %d",
                     flagged_count, len(results) - flagged_count, len(results))

        # Post-rule velocity/structuring check: aggregate analysis per customer
        upload_id = state["upload_id"]
        ref_row = await db.execute(
            select(func.max(TxnModel.date)).where(TxnModel.upload_id == upload_id)
        )
        ref_date_str = ref_row.scalar()
        ref_date = datetime.fromisoformat(ref_date_str) if ref_date_str else datetime.now(UTC)

        txn_rows = await db.execute(
            select(TxnModel.customer_id, TxnModel.amount, TxnModel.date, TxnModel.id)
            .where(TxnModel.upload_id == upload_id)
        )
        all_txns = txn_rows.all()

        cust_txns: dict[str, list] = defaultdict(list)
        for t in all_txns:
            cust_txns[t.customer_id].append({"id": t.id, "amount": t.amount, "date": t.date})

        setattr_rules: dict[str, dict[str, str]] = {}

        for cid, txns in cust_txns.items():
            amounts_30d = [t["amount"] for t in txns
                          if t["date"] and datetime.fromisoformat(t["date"]) >= (ref_date - timedelta(days=30))]
            if not amounts_30d:
                continue

            one_day_ago = ref_date - timedelta(days=1)
            structuring_count = sum(1 for t in txns
                                    if t["date"] and datetime.fromisoformat(t["date"]) >= one_day_ago
                                    and t["amount"] is not None and 9000 <= t["amount"] <= 10000)

            one_week_ago = ref_date - timedelta(days=7)
            four_weeks_ago = ref_date - timedelta(days=35)
            this_week_count = sum(1 for t in txns
                                  if t["date"] and datetime.fromisoformat(t["date"]) >= one_week_ago)
            weekly_buckets = [0, 0, 0, 0]
            for t in txns:
                if not t["date"]:
                    continue
                dt = datetime.fromisoformat(t["date"])
                if dt < one_week_ago and dt >= four_weeks_ago:
                    weeks_ago = int((ref_date - dt).days // 7)
                    if 1 <= weeks_ago <= 4:
                        weekly_buckets[weeks_ago - 1] += 1
            WEEKS_PRIOR = 4.0
            avg_weekly = sum(weekly_buckets) / WEEKS_PRIOR
            velocity_zscore = None
            if avg_weekly > 0 and this_week_count > 0:
                variance = sum((c - avg_weekly) ** 2 for c in weekly_buckets) / WEEKS_PRIOR
                std_weekly = math.sqrt(variance) if variance > 0 else 1.0
                velocity_zscore = (this_week_count - avg_weekly) / max(std_weekly, 1.0)

            if velocity_zscore is not None and velocity_zscore > get_velocity_zscore_threshold():
                for t in txns:
                    setattr_rules.setdefault(t["id"], {})["velocity_zscore"] = (
                        f"Velocity Check (z-score: {velocity_zscore:.1f})"
                    )
            if structuring_count >= get_structuring_24h_threshold():
                for t in txns:
                    if t["date"] and datetime.fromisoformat(t["date"]) >= one_day_ago:
                        setattr_rules.setdefault(t["id"], {})["structuring_24h"] = (
                            f"Structuring 24h ({structuring_count} txns near threshold)"
                        )

        for r in results:
            new_flags = setattr_rules.get(r["transaction_id"])
            if new_flags:
                if r["flag_details"] is None:
                    r["flag_details"] = {}
                r["flag_details"].update(new_flags)
                r["status"] = "flagged"

        flagged_count = sum(1 for r in results if r["status"] == "flagged")
        logger.info("Rule engine: %d flagged, %d clean out of %d",
                     flagged_count, len(results) - flagged_count, len(results))

        now = _now()
        objs: list[ValidationResult] = []
        for r in results:
            objs.append(ValidationResult(
                upload_id=r["upload_id"],
                transaction_id=r["transaction_id"],
                status=r["status"],
                flag_details=r.get("flag_details"),
                validated_at=r["validated_at"],
                created_at=r.get("created_at", r["validated_at"]),
                updated_at=r.get("updated_at", r["validated_at"]),
            ))
        db.add_all(objs)
        await db.flush()

        for r in results:
            await record_transaction_status(db, r["transaction_id"], r["status"])

        await db.commit()
        return {"results": results}

    return await run_node(state, db, "rule_engine_batch", impl)
