"""Run the eval harness — upload a fraud dataset, run the workflow, evaluate results.

Usage:
    python -m scripts.run_eval --csv data/fraud_dataset.csv --manifest data/fraud_dataset.manifest.json
    python -m scripts.run_eval --generate --count 5000         # generate + eval in one step
"""

import argparse
import asyncio
import json
import uuid
from datetime import datetime, UTC
from pathlib import Path

from sqlalchemy import select

from src.aml_workflow.eval import EvalReport, PatternMetrics, _compute_metrics
from src.aml_workflow.eval.hallucination import check_sar as check_hallucination
from src.aml_workflow.eval.completeness import check_sar as check_completeness
from src.aml_workflow.triggers import run_validation
from src.core.models.validation_result import ValidationResult
from src.bff.database import async_session_factory
from src.core.models.transaction import Transaction
from src.core.models.uploaded_files import UploadedFiles
from src.file_processor.service import process_upload
from src.core.models.sar import SAR
from tests.helpers import upload_csv as _upload_csv


async def evaluate(
    csv_path: str,
    manifest_path: str | None,
    upload_csv: bool = True,
) -> EvalReport:
    """Run the full eval pipeline: upload → workflow → evaluate."""
    with open(manifest_path, "r") as f:
        manifest: dict[str, str] = json.load(f)

    async with async_session_factory() as session:
        if upload_csv:
            csv_file = Path(csv_path)
            if not csv_file.exists():
                raise FileNotFoundError(f"CSV not found: {csv_path}")
            uid = await _upload_csv(session, csv_file)
        else:
            uid = csv_path

        # Run workflow with fallback LLM (no API keys)
        await run_validation(uid, session)

        upload = await session.get(UploadedFiles, uid)
        report = EvalReport(upload_id=uid)

        # ── Load all transactions ───────────────────────────────
        txns = (await session.execute(
            select(Transaction).where(Transaction.upload_id == uid)
        )).scalars().all()
        report.total_transactions = len(txns)

        # ── Get validation results ──────────────────────────────
        vrs = (await session.execute(
            select(ValidationResult).where(ValidationResult.upload_id == uid)
        )).scalars().all()
        flagged_vrs = [vr for vr in vrs if vr.status == "flagged"]
        report.total_flagged = len(flagged_vrs)

        # ── Build lookup maps ───────────────────────────────────
        txn_by_id = {t.id: t for t in txns}
        flagged_txn_ids = {vr.transaction_id for vr in flagged_vrs}

        # ── Pattern-level metrics ───────────────────────────────
        pattern_ground_truth: dict[str, set[str]] = {}
        for src_txn_id, pattern in manifest.items():
            pattern_ground_truth.setdefault(pattern, set()).add(src_txn_id)

        for pattern, txn_ids in pattern_ground_truth.items():
            total = len(txn_ids)
            flagged = sum(
                1 for t in txns
                if t.source_txn_id in txn_ids and t.id in flagged_txn_ids
            )
            prec, rec, f1 = _compute_metrics(total, flagged)
            report.pattern_metrics.append(PatternMetrics(
                pattern=pattern, total=total, flagged=flagged,
                precision=prec, recall=rec, f1=f1,
            ))

        total_anomalous = sum(pm.total for pm in report.pattern_metrics)
        total_flagged_anomalous = sum(pm.flagged for pm in report.pattern_metrics)
        report.total_anomalous = total_anomalous
        report.overall_precision, report.overall_recall, report.overall_f1 = \
            _compute_metrics(total_anomalous, total_flagged_anomalous)

        # ── Hallucination check ─────────────────────────────────
        sars = (await session.execute(
            select(SAR).where(SAR.upload_id == uid)
        )).scalars().all()

        passed_hallucination = 0
        total_completeness_score = 0.0

        for sar in sars:
            if sar.transaction_id in txn_by_id:
                txn = txn_by_id[sar.transaction_id]
                txn_dict = {
                    "source_txn_id": txn.source_txn_id,
                    "account_id": txn.account_id,
                    "amount": txn.amount,
                    "counterparty": txn.counterparty,
                    "city": txn.city,
                    "state": txn.state,
                    "country": txn.country,
                    "date": txn.date,
                }
                # Find flag_details for this txn
                flag_details = None
                for vr in flagged_vrs:
                    if vr.transaction_id == sar.transaction_id:
                        flag_details = vr.flag_details
                        break

                hl_result = await check_hallucination(
                    sar.id, sar.transaction_id, sar.content, txn_dict, flag_details
                )
                report.hallucination_results.append(hl_result)
                if hl_result.passed:
                    passed_hallucination += 1

                comp_result = await check_completeness(
                    sar.id, sar.transaction_id, sar.content, flag_details
                )
                report.completeness_results.append(comp_result)
                total_completeness_score += comp_result.score

        report.hallucination_free_rate = passed_hallucination / max(len(sars), 1)
        report.avg_completeness = total_completeness_score / max(len(sars), 1)

        return report


async def main_async(args):
    if args.generate:
        print("Generating fraud dataset...")
        import scripts.test_generate_fraud_data as gfd
        csv_path = args.csv or "work/fraud_eval.csv"
        manifest_path = args.manifest or "work/fraud_eval.manifest.json"
        await gfd.generate(args.count, csv_path, manifest_path, seed_rules=True)
    else:
        csv_path = args.csv
        manifest_path = args.manifest or f"{Path(csv_path).with_suffix('').as_posix()}.manifest.json"

    print(f"Evaluating: CSV={csv_path}, Manifest={manifest_path}")
    report = await evaluate(csv_path, manifest_path)
    print("\n" + report.summary())

    report_json = Path(csv_path).with_suffix(".eval.json")
    import dataclasses
    with open(report_json, "w") as f:
        json.dump(dataclasses.asdict(report), f, indent=2, default=str)
    print(f"Report saved to {report_json}")


def main():
    parser = argparse.ArgumentParser(description="Run AML workflow eval harness")
    parser.add_argument("--csv", type=str, default=None, help="Path to CSV to evaluate")
    parser.add_argument("--manifest", type=str, default=None, help="Path to ground truth manifest JSON")
    parser.add_argument("--generate", action="store_true", help="Generate fraud dataset before evaluating")
    parser.add_argument("--count", type=int, default=1000, help="Total transactions (default: 1000)")
    args = parser.parse_args()

    if not args.csv and not args.generate:
        parser.error("Provide --csv or --generate")

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
