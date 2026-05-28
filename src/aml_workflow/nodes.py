from __future__ import annotations

import asyncio
import json
import logging
import math
from collections import defaultdict
from datetime import datetime, UTC, timedelta
from typing import Any, Callable

from langgraph.errors import GraphInterrupt
from langgraph.types import interrupt
from sqlalchemy import select, func, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.llm import LLMClient
from src.aml_workflow.services import _set_upload_status, record_transaction_status
from src.aml_workflow.state import WorkflowState
from src.aml_workflow.validator import evaluate_rules
from src.bff.config import get_velocity_zscore_threshold, get_structuring_24h_threshold
from src.bff.logger import logger

MAX_RETRIES = 3

_LIBRARY_TRANSIENT_NAMES = {
    "OperationalError",
    "ConnectError",
    "APITimeoutError",
    "APIConnectionError",
    "RateLimitError",
    "InternalServerError",
}


def _is_transient(e: Exception) -> bool:
    if isinstance(e, (TimeoutError, ConnectionError)):
        return True
    return any(cls.__name__ in _LIBRARY_TRANSIENT_NAMES for cls in type(e).__mro__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def run_node(state: WorkflowState, db: AsyncSession, step_name: str, fn: Callable) -> dict:
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = await fn(state)
            return result
        except GraphInterrupt:
            raise
        except Exception as e:
            last_exc = e
            if _is_transient(e) and attempt < MAX_RETRIES:
                await db.rollback()
                logger.warning(
                    "%s failed (attempt %d/%d): %s: %s",
                    step_name, attempt + 1, MAX_RETRIES + 1,
                    type(e).__name__, e,
                )
                await asyncio.sleep(2 ** attempt)
            else:
                break

    logger.error(
        "%s failed permanently: %s: %s",
        step_name, type(last_exc).__name__, last_exc,
        exc_info=last_exc,
    )
    raise last_exc


# ── Graph nodes ────────────────────────────────────────────────

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
            {"id": r.id, "name": r.name, "rules_json": r.rules_json}
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


async def enrich_node(state: WorkflowState, db: AsyncSession, llm: LLMClient | None, mode: str) -> dict:
    async def impl(state: WorkflowState) -> dict:
        from src.aml_workflow.enrichment import enrich_transactions

        flagged_ids = {r["transaction_id"] for r in state["results"] if r["status"] == "flagged"}
        flagged_txns = [{**t, "status": "flagged"} for t in state["transactions"] if t["id"] in flagged_ids]
        enriched = await enrich_transactions(db, flagged_txns, state["upload_id"])
        logger.info("Enriched %d customers for upload %s", len(enriched), state["upload_id"])
        return {"enriched_data": enriched}

    return await run_node(state, db, "enrich_node", impl)


async def stage2_triage_node(state: WorkflowState, db: AsyncSession, llm: LLMClient | None, mode: str) -> dict:
    async def impl(state: WorkflowState) -> dict:
        from src.core.models.transaction import Transaction as TxnModel
        from src.core.models.validation_result import ValidationResult

        flagged = [r for r in state["results"] if r["status"] == "flagged"]
        now = _now()

        llm_batch: list[tuple[dict, dict, dict, dict | None]] = []
        bypasses: list[tuple[dict, dict]] = []

        for result in flagged:
            txn_id = result["transaction_id"]
            txn = next((t for t in state["transactions"] if t["id"] == txn_id), None)
            if txn is None:
                continue

            if mode == "stage1":
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


async def sar_node(state: WorkflowState, db: AsyncSession, llm: LLMClient | None, mode: str) -> dict:
    PLACEHOLDER_SAR = "Auto-flagged for human review"
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


# ── Routing helpers ───────────────────────────────────────────

def has_flagged(state: WorkflowState, mode: str) -> str:
    results = state.get("results", [])
    flagged = [r for r in results if r["status"] == "flagged"]
    return "stage2" if flagged else "skip"


def has_escalated(state: WorkflowState, mode: str) -> str:
    results = state.get("results", [])
    escalated = [r for r in results if r.get("risk_level") == "high"]
    if not escalated:
        return "skip"
    if mode in ("stage3", "full"):
        return "stage3"
    return "sar"


def needs_sar(state: WorkflowState, mode: str) -> str:
    results = state.get("results", [])
    needs = [r for r in results if r.get("risk_level") == "high"]
    return "sar" if needs else "skip"
