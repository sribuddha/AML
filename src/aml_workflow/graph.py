import asyncio
import json
import logging
from datetime import datetime, UTC

from langgraph.errors import GraphInterrupt
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.llm import LLMClient
from src.bff.logger import logger
from src.aml_workflow.state import WorkflowState
from src.aml_workflow.validator import evaluate_rules

MAX_RETRIES = 3

TRANSIENT_ERRORS = {
    "TimeoutError",
    "OperationalError",
    "ConnectError",
    "APITimeoutError",
    "APIConnectionError",
    "RateLimitError",
    "InternalServerError",
}


def _is_transient(e: Exception) -> bool:
    return type(e).__name__ in TRANSIENT_ERRORS


def _now() -> str:
    return datetime.now(UTC).isoformat()


def create_workflow(db: AsyncSession, llm: LLMClient | None = None, mode: str = "full", checkpointer=None):
    if llm is None:
        llm = LLMClient()
    PLACEHOLDER_SAR = "Auto-flagged for human review"

    async def _run_node(state: WorkflowState, step_name: str, fn):
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

    async def load_data(state: WorkflowState) -> dict:
        from src.aml_workflow.models.rule import Rule
        from src.aml_workflow.models.validation_result import ValidationResult
        from src.file_processor.models import Transaction

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

    async def rule_engine_batch(state: WorkflowState) -> dict:
        from src.file_processor.models import Transaction as TxnModel
        from src.aml_workflow.models.transaction_status import TransactionStatus
        from src.aml_workflow.models.validation_result import ValidationResult

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
        logger.info("Rule engine: %d flagged, %d clean out of %d", flagged_count, len(results) - flagged_count, len(results))

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
            txn_id = r["transaction_id"]
            new_status = r["status"]
            db.add(TransactionStatus(
                transaction_id=txn_id,
                status=new_status,
                actor="system",
                created_at=now,
            ))

        await db.commit()
        return {"results": results}

    async def enrich_node(state: WorkflowState) -> dict:
        from src.aml_workflow.enrichment import enrich_transactions

        flagged_ids = {r["transaction_id"] for r in state["results"] if r["status"] == "flagged"}
        flagged_txns = [{**t, "status": "flagged"} for t in state["transactions"] if t["id"] in flagged_ids]
        enriched = await enrich_transactions(db, flagged_txns, state["upload_id"])
        logger.info("Enriched %d customers for upload %s", len(enriched), state["upload_id"])
        return {"enriched_data": enriched}

    async def stage2_triage(state: WorkflowState) -> dict:
        from src.file_processor.models import Transaction as TxnModel
        from src.aml_workflow.models.transaction_status import TransactionStatus
        from src.aml_workflow.models.validation_result import ValidationResult
        from sqlalchemy import update as sa_update

        flagged = [r for r in state["results"] if r["status"] == "flagged"]
        now = _now()

        for result in flagged:
            txn_id = result["transaction_id"]
            txn = next((t for t in state["transactions"] if t["id"] == txn_id), None)
            if txn is None:
                continue

            if mode == "stage1":
                from src.aml_workflow.llm import TriageDecision
                decision = TriageDecision(
                    escalate=True,
                    reason="Escalated to human review (Stage 1 mode)",
                    confidence=0.5,
                )
            else:
                flag_details = result.get("flag_details") or {}
                enriched = state.get("enriched_data", {})
                customer_id = txn.get("customer_id", "")
                enriched_context = enriched.get(customer_id) if enriched else None
                decision = await llm.triage(txn, flag_details, rules=state["rules"], enriched_context=enriched_context)

            if decision.escalate:
                result["risk_level"] = "high"
            else:
                result["risk_level"] = "auto_reviewed"
            result["triage_reasoning"] = decision.reason

            new_status = "escalated" if decision.escalate else "clean"
            db.add(TransactionStatus(
                transaction_id=txn_id,
                status=new_status,
                actor="system",
                created_at=now,
            ))

            await db.execute(
                sa_update(ValidationResult)
                .where(ValidationResult.transaction_id == txn_id, ValidationResult.upload_id == state["upload_id"])
                .values(risk_level=result["risk_level"], triage_reasoning=decision.reason, raw_llm_response=decision.raw_response, updated_at=now)
            )

        await db.commit()

        escalated_count = sum(1 for r in flagged if r.get("risk_level") == "high")
        logger.info("Stage2 triage: %d escalated, %d auto-reviewed out of %d flagged",
                     escalated_count, len(flagged) - escalated_count, len(flagged))

        return {"triage_results": {r["transaction_id"]: r for r in flagged}}

    async def stage3_triage(state: WorkflowState) -> dict:
        from src.file_processor.models import Transaction
        from src.aml_workflow.models.transaction_status import TransactionStatus
        from src.aml_workflow.models.validation_result import ValidationResult
        from sqlalchemy import update as sa_update

        escalated = [r for r in state["results"] if r.get("risk_level") == "high"]
        if not escalated:
            return {}

        now = _now()
        for result in escalated:
            txn_id = result["transaction_id"]
            txn = next((t for t in state["transactions"] if t["id"] == txn_id), None)
            if txn is None:
                continue

            flag_details = result.get("flag_details") or {}

            if mode in ("stage3", "full"):
                recent_txns = (
                    await db.execute(
                        select(Transaction).where(
                            Transaction.customer_id == txn["customer_id"],
                            Transaction.id != txn_id,
                        ).order_by(Transaction.date.desc()).limit(20)
                    )
                ).scalars().all()

                recent_list = [
                    {"amount": t.amount, "counterparty": t.counterparty,
                     "city": t.city, "state": t.state, "country": t.country, "date": t.date}
                    for t in recent_txns
                ]

                decision = await llm.triage_stage3(txn, flag_details, recent_list, rules=state["rules"])
            else:
                from src.aml_workflow.llm import TriageDecision
                decision = TriageDecision(
                    escalate=True,
                    reason="Escalated (mode bypasses stage3 analysis)",
                    confidence=0.5,
                )

            new_status = "pending_review" if decision.escalate else "clean"
            risk_level = "high" if decision.escalate else "auto_reviewed"

            result["risk_level"] = risk_level
            result["triage_reasoning"] = decision.reason
            result["sar_content"] = decision.reason if decision.escalate else ""

            db.add(TransactionStatus(
                transaction_id=txn_id,
                status=new_status,
                actor="system",
                created_at=now,
            ))

            await db.execute(
                sa_update(ValidationResult)
                .where(ValidationResult.transaction_id == txn_id, ValidationResult.upload_id == state["upload_id"])
                .values(risk_level=risk_level, triage_reasoning=decision.reason, raw_llm_response=decision.raw_response, updated_at=now)
            )

        await db.commit()

        pending_count = sum(1 for r in escalated if r.get("risk_level") == "high")
        logger.info("Stage3 triage: %d pending_review, %d cleared out of %d escalated",
                     pending_count, len(escalated) - pending_count, len(escalated))

        return {}

    async def sar_node(state: WorkflowState) -> dict:
        from src.aml_workflow.models.sar import SAR
        from src.aml_workflow.models.transaction_status import TransactionStatus
        from src.aml_workflow.models.upload_status import UploadStatus
        from src.file_processor.models import UploadedFiles

        now = _now()
        sars: list[dict] = []

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
                    confidence=0.0,
                )
                sar_result = await llm.generate_sar(txn, flag_details, triage)
                content = sar_result.content
                raw_llm_response = sar_result.raw_response
            else:
                content = PLACEHOLDER_SAR
                raw_llm_response = None

            rule_id = next(iter(flag_details.keys()), None) if flag_details else None

            sars.append({
                "transaction_id": txn_id,
                "upload_id": state["upload_id"],
                "rule_id": rule_id,
                "content": content,
                "raw_llm_response": raw_llm_response,
                "status": "pending_review",
                "created_at": now,
                "updated_at": now,
            })

        if sars:
            objs = [SAR(**s) for s in sars]
            db.add_all(objs)
            await db.flush()

            for sar_obj in objs:
                db.add(TransactionStatus(
                    transaction_id=sar_obj.transaction_id,
                    status="pending_review",
                    actor="system",
                    created_at=now,
                ))

            upload = await db.get(UploadedFiles, state["upload_id"])
            if upload:
                upload.status = "pending_human"
                upload.updated_at = now
                db.add(UploadStatus(
                    upload_id=state["upload_id"],
                    status="pending_human",
                    actor="system",
                    created_at=now,
                ))

            await db.commit()
            logger.info("Created %d SARs for upload %s", len(sars), state["upload_id"])

        return {"sars": sars}

    async def human_review(state: WorkflowState) -> dict:
        sars = state.get("sars", [])
        if not sars:
            return {"human_review_complete": True}

        from sqlalchemy import func, select
        from src.aml_workflow.models.sar import SAR
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

    async def finalize(state: WorkflowState) -> dict:
        from src.aml_workflow.models.upload_status import UploadStatus
        from src.file_processor.models import UploadedFiles

        upload = await db.get(UploadedFiles, state["upload_id"])
        if upload is None:
            return {}

        human_reviewed = state.get("human_review_complete", False)
        has_sars = bool(state.get("sars"))

        if has_sars and not human_reviewed:
            upload.status = "pending_human"
        else:
            upload.status = "complete"

        now = _now()
        upload.updated_at = now
        db.add(UploadStatus(
            upload_id=state["upload_id"],
            status=upload.status,
            actor="system",
            created_at=now,
        ))
        await db.commit()

        logger.info("Upload %s status: %s", state["upload_id"], upload.status)
        return {}

    # ── Routing helpers ───────────────────────────────────────────

    def _has_flagged(state: WorkflowState) -> str:
        results = state.get("results", [])
        flagged = [r for r in results if r["status"] == "flagged"]
        return "stage2" if flagged else "skip"

    def _has_escalated(state: WorkflowState) -> str:
        results = state.get("results", [])
        escalated = [r for r in results if r.get("risk_level") == "high"]
        if not escalated:
            return "skip"
        if mode in ("stage3", "full"):
            return "stage3"
        return "sar"

    def _needs_sar(state: WorkflowState) -> str:
        results = state.get("results", [])
        needs = [r for r in results if r.get("risk_level") == "high"]
        return "sar" if needs else "skip"

    # ── Wrap nodes with retry ────────────────────────────────────

    def _wrap(name: str, fn):
        async def wrapped(state: WorkflowState) -> dict:
            return await _run_node(state, name, fn)
        return wrapped

    # ── Build graph ──────────────────────────────────────────────

    builder = StateGraph(WorkflowState)

    builder.add_node("load_data", _wrap("load_data", load_data))
    builder.add_node("rule_engine_batch", _wrap("rule_engine_batch", rule_engine_batch))
    builder.add_node("enrich_node", _wrap("enrich_node", enrich_node))
    builder.add_node("stage2_triage", _wrap("stage2_triage", stage2_triage))
    builder.add_node("stage3_triage", _wrap("stage3_triage", stage3_triage))
    builder.add_node("sar_node", _wrap("sar_node", sar_node))
    builder.add_node("human_review", _wrap("human_review", human_review))
    builder.add_node("finalize", _wrap("finalize", finalize))

    builder.set_entry_point("load_data")
    builder.add_edge("load_data", "rule_engine_batch")
    builder.add_conditional_edges(
        "rule_engine_batch",
        _has_flagged,
        {"stage2": "enrich_node", "skip": "finalize"},
    )
    builder.add_edge("enrich_node", "stage2_triage")
    builder.add_conditional_edges(
        "stage2_triage",
        _has_escalated,
        {"stage3": "stage3_triage", "sar": "sar_node", "skip": "finalize"},
    )
    builder.add_conditional_edges(
        "stage3_triage",
        _needs_sar,
        {"sar": "sar_node", "skip": "finalize"},
    )
    builder.add_edge("sar_node", "human_review")
    builder.add_edge("human_review", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)
