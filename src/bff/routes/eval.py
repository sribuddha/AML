import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.eval import _compute_metrics
from src.aml_workflow.eval.completeness import check_sar as check_completeness
from src.aml_workflow.eval.hallucination import check_sar as check_hallucination
from src.core.models.sar import SAR
from src.core.models.validation_result import ValidationResult
from src.bff.database import get_db
from src.core.schemas import (
    EvalReportResponse,
    PatternMetricsResponse,
    StageMetricsResponse,
)
from src.core.models.transaction import Transaction
from src.core.models.uploaded_files import UploadedFiles

router = APIRouter()

_STAGE_INFERRED: dict[str, str] = {}


def _infer_stage(entry: dict) -> str:
    if "stage" in entry:
        return entry["stage"]
    scenario = entry.get("scenario", "")
    src_id = entry.get("source_txn_id", "")
    if scenario.startswith("STAGE1_") or src_id.startswith("ST1_"):
        return "stage1"
    if scenario.startswith("STAGE2_") or src_id.startswith("ST2_"):
        return "stage2"
    if scenario.startswith("STAGE3_") or src_id.startswith("ST3_"):
        return "stage3"
    return "unknown"


def _load_eval_entries(eval_path: str) -> list[dict]:
    path = Path(eval_path)
    if not path.exists():
        return []
    if eval_path.endswith(".manifest.json"):
        with open(path) as f:
            obj = json.load(f)
        return [{"source_txn_id": txn_id, "scenario": label, "expected_escalate": True}
                for txn_id, label in obj.items()]
    entries: list[dict] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


@router.post("/api/uploads/{upload_id}/eval")
async def evaluate_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
) -> EvalReportResponse:
    upload = await db.get(UploadedFiles, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    if not upload.eval_file:
        raise HTTPException(status_code=400, detail="No eval data associated with this upload")

    mode = upload.mode or "full"

    eval_entries = _load_eval_entries(upload.eval_file)
    if not eval_entries:
        raise HTTPException(status_code=400, detail="Eval file is empty or not found")

    expected = {e["source_txn_id"]: e for e in eval_entries}

    txn_rows = await db.execute(
        select(Transaction).where(Transaction.upload_id == upload_id)
    )
    transactions = txn_rows.scalars().all()
    txn_map = {t.source_txn_id: t for t in transactions}

    txn_ids = [t.id for t in transactions]
    vr_rows = await db.execute(
        select(ValidationResult).where(ValidationResult.transaction_id.in_(txn_ids))
    )
    vr_map = {vr.transaction_id: vr for vr in vr_rows.scalars().all()}

    sar_rows = await db.execute(
        select(SAR).where(SAR.upload_id == upload_id)
    )
    sars = sar_rows.scalars().all()
    sar_by_txn = {s.transaction_id: s for s in sars}

    # Group entries by stage
    stage_groups: dict[str, dict[str, dict]] = {}
    for src_id, exp in expected.items():
        stage = _infer_stage(exp)
        if stage not in stage_groups:
            stage_groups[stage] = {"total": 0, "flagged": 0, "escalated": 0, "auto_reviewed": 0, "patterns": {}}

        pattern = exp.get("scenario", "unknown")
        if pattern not in stage_groups[stage]["patterns"]:
            stage_groups[stage]["patterns"][pattern] = {"total": 0, "flagged": 0}

        txn = txn_map.get(src_id)
        if txn is None:
            continue

        stage_groups[stage]["total"] += 1
        stage_groups[stage]["patterns"][pattern]["total"] += 1

        vr = vr_map.get(txn.id)
        if vr is None:
            continue
        if vr.status == "flagged":
            stage_groups[stage]["flagged"] += 1
            stage_groups[stage]["patterns"][pattern]["flagged"] += 1
            if vr.risk_level == "high":
                stage_groups[stage]["escalated"] += 1
            elif vr.risk_level == "auto_reviewed":
                stage_groups[stage]["auto_reviewed"] += 1

    flagged_total = sum(g["flagged"] for g in stage_groups.values())
    anomalous_total = sum(g["total"] for g in stage_groups.values())

    # Build per-stage metrics
    stage_metrics: list[StageMetricsResponse] = []
    all_pattern_metrics: list[PatternMetricsResponse] = []

    for stage_name in sorted(stage_groups.keys()):
        sg = stage_groups[stage_name]
        total = sg["total"]
        flagged = sg["flagged"]
        escalated = sg["escalated"]
        auto_reviewed = sg["auto_reviewed"]

        rule_catch_rate = flagged / total if total > 0 else 0.0
        llm_clear_rate = (auto_reviewed / flagged) if flagged > 0 else None
        llm_escalate_rate = (escalated / flagged) if flagged > 0 else None

        pattern_metrics = []
        for pattern, counts in sorted(sg["patterns"].items()):
            prec, rec, f1 = _compute_metrics(counts["total"], counts["flagged"])
            pm = PatternMetricsResponse(
                pattern=pattern,
                total=counts["total"],
                flagged=counts["flagged"],
                precision=prec,
                recall=rec,
                f1=f1,
            )
            pattern_metrics.append(pm)
            all_pattern_metrics.append(pm)

        stage_metrics.append(StageMetricsResponse(
            stage=stage_name,
            total=total,
            flagged=flagged,
            escalated=escalated,
            auto_reviewed=auto_reviewed,
            rule_catch_rate=round(rule_catch_rate, 4),
            llm_clear_rate=round(llm_clear_rate, 4) if llm_clear_rate is not None else None,
            llm_escalate_rate=round(llm_escalate_rate, 4) if llm_escalate_rate is not None else None,
            pattern_metrics=pattern_metrics,
        ))

    # Hallucination checks
    hallucination_results = []
    for sar in sars:
        txn = next((t for t in transactions if t.id == sar.transaction_id), None)
        if txn is None:
            continue
        vr = vr_map.get(txn.id)
        flag_dict = {}
        if vr and vr.flag_details:
            if isinstance(vr.flag_details, dict):
                flag_dict = {str(k): str(v) for k, v in vr.flag_details.items()}

        related_txns = [
            {"source_txn_id": rt.source_txn_id, "amount": rt.amount, "counterparty": rt.counterparty}
            for rt in transactions
            if rt.id != sar.transaction_id and rt.customer_id == txn.customer_id
        ]

        txn_dict = {
            "source_txn_id": txn.source_txn_id,
            "account_id": txn.account_id,
            "customer_id": txn.customer_id,
            "amount": txn.amount,
            "counterparty": txn.counterparty,
            "city": txn.city,
            "state": txn.state,
            "country": txn.country,
            "date": txn.date,
        }
        result = await check_hallucination(
            sar_id=sar.id,
            transaction_id=sar.transaction_id,
            narrative=sar.content,
            transaction=txn_dict,
            flag_details=flag_dict,
            related_transactions=related_txns,
        )
        hallucination_results.append({
            "sar_id": result.sar_id,
            "transaction_id": result.transaction_id,
            "hallucinated_facts": result.hallucinated_facts,
            "passed": result.passed,
        })

    # Completeness checks
    completeness_results = []
    for sar in sars:
        txn = next((t for t in transactions if t.id == sar.transaction_id), None)
        if txn is None:
            continue
        vr = vr_map.get(txn.id)
        flag_dict = {}
        if vr and vr.flag_details:
            if isinstance(vr.flag_details, dict):
                flag_dict = {str(k): str(v) for k, v in vr.flag_details.items()}
        result = await check_completeness(
            sar_id=sar.id,
            transaction_id=sar.transaction_id,
            narrative=sar.content,
            flag_details=flag_dict,
        )
        completeness_results.append({
            "sar_id": result.sar_id,
            "transaction_id": result.transaction_id,
            "covered_rules": result.covered_rules,
            "missed_rules": result.missed_rules,
            "score": result.score,
        })

    # Overall metrics (backward compat)
    total = len(all_pattern_metrics)
    overall_prec = sum(p.precision for p in all_pattern_metrics) / total if total > 0 else 0.0
    overall_rec = sum(p.recall for p in all_pattern_metrics) / total if total > 0 else 0.0
    overall_f1 = sum(p.f1 for p in all_pattern_metrics) / total if total > 0 else 0.0

    hf_total = len(hallucination_results)
    hf_passed = sum(1 for h in hallucination_results if h["passed"])
    hf_rate = hf_passed / hf_total if hf_total > 0 else 1.0

    comp_total = len(completeness_results)
    avg_comp = sum(c["score"] for c in completeness_results) / comp_total if comp_total > 0 else 1.0

    return EvalReportResponse(
        upload_id=upload_id,
        mode=mode,
        total_transactions=len(transactions),
        total_anomalous=anomalous_total,
        total_flagged=flagged_total,
        stage_metrics=stage_metrics,
        pattern_metrics=all_pattern_metrics,
        hallucination_results=hallucination_results,
        completeness_results=completeness_results,
        overall_precision=round(overall_prec, 4),
        overall_recall=round(overall_rec, 4),
        overall_f1=round(overall_f1, 4),
        hallucination_free_rate=round(hf_rate, 4),
        avg_completeness=round(avg_comp, 4),
    )
