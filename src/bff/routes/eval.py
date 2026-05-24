import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.eval import _compute_metrics
from src.aml_workflow.eval.completeness import check_sar as check_completeness
from src.aml_workflow.eval.hallucination import check_sar as check_hallucination
from src.aml_workflow.models.sar import SAR
from src.aml_workflow.models.validation_result import ValidationResult
from src.bff.database import get_db
from src.bff.schemas import EvalReportResponse
from src.file_processor.models import Transaction, UploadedFiles

router = APIRouter()


def _load_eval_entries(eval_path: str) -> list[dict]:
    path = Path(eval_path)
    if not path.exists():
        return []
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

    # Compute pattern metrics
    pattern_groups: dict[str, dict] = {}
    flagged_total = 0
    anomalous_total = len(eval_entries)

    for src_id, exp in expected.items():
        pattern = exp.get("scenario", "unknown")
        if pattern not in pattern_groups:
            pattern_groups[pattern] = {"total": 0, "flagged": 0}

        pattern_groups[pattern]["total"] += 1

        txn = txn_map.get(src_id)
        if txn is None:
            continue
        vr = vr_map.get(txn.id)
        if vr is None:
            continue
        if vr.risk_level == "high":
            pattern_groups[pattern]["flagged"] += 1
            flagged_total += 1

    pattern_metrics = []
    for pattern, counts in sorted(pattern_groups.items()):
        prec, rec, f1 = _compute_metrics(counts["total"], counts["flagged"])
        pattern_metrics.append({
            "pattern": pattern,
            "total": counts["total"],
            "flagged": counts["flagged"],
            "precision": prec,
            "recall": rec,
            "f1": f1,
        })

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

    # Overall metrics
    total = len(pattern_groups)
    overall_prec = sum(p["precision"] for p in pattern_metrics) / total if total > 0 else 0.0
    overall_rec = sum(p["recall"] for p in pattern_metrics) / total if total > 0 else 0.0
    overall_f1 = sum(p["f1"] for p in pattern_metrics) / total if total > 0 else 0.0

    hf_total = len(hallucination_results)
    hf_passed = sum(1 for h in hallucination_results if h["passed"])
    hf_rate = hf_passed / hf_total if hf_total > 0 else 1.0

    comp_total = len(completeness_results)
    avg_comp = sum(c["score"] for c in completeness_results) / comp_total if comp_total > 0 else 1.0

    return EvalReportResponse(
        upload_id=upload_id,
        total_transactions=len(transactions),
        total_anomalous=anomalous_total,
        total_flagged=flagged_total,
        pattern_metrics=pattern_metrics,
        hallucination_results=hallucination_results,
        completeness_results=completeness_results,
        overall_precision=round(overall_prec, 4),
        overall_recall=round(overall_rec, 4),
        overall_f1=round(overall_f1, 4),
        hallucination_free_rate=round(hf_rate, 4),
        avg_completeness=round(avg_comp, 4),
    )
