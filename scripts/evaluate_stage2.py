"""Compare LLM triage decisions against .eval expectations.

Usage:
    python -m scripts.evaluate_stage2 --upload-id <UUID> --eval upload.eval
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.bff.database import async_session_factory
from src.file_processor.models import Transaction
from src.aml_workflow.models.validation_result import ValidationResult


def _load_eval(path: Path) -> list[dict]:
    entries: list[dict] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


async def evaluate(upload_id: str, eval_path: Path):
    entries = _load_eval(eval_path)
    if not entries:
        print("ERROR: No entries found in eval file.")
        return

    # Build lookup: source_txn_id -> eval entry
    expected = {e["source_txn_id"]: e for e in entries}

    async with async_session_factory() as db:
        # Fetch all transactions + validation results for this upload
        stmt = (
            select(Transaction)
            .where(Transaction.upload_id == upload_id)
        )
        txn_rows = await db.execute(stmt)
        transactions = txn_rows.scalars().all()

        if not transactions:
            print(f"ERROR: No transactions found for upload {upload_id}")
            return

        # Build lookup: source_txn_id -> transaction_id
        txn_map = {t.source_txn_id: t.id for t in transactions}

        # Fetch validation results for all transaction IDs
        txn_ids = list(txn_map.values())
        vr_stmt = select(ValidationResult).where(
            ValidationResult.transaction_id.in_(txn_ids)
        )
        vr_rows = await db.execute(vr_stmt)
        vr_map = {vr.transaction_id: vr for vr in vr_rows.scalars().all()}

    # Compare
    passed = 0
    failed = 0
    skipped = 0
    results: list[dict] = []

    for src_id, exp in expected.items():
        txn_id = txn_map.get(src_id)
        if not txn_id:
            results.append({
                "source_txn_id": src_id,
                "scenario": exp.get("scenario", "?"),
                "expected": exp["expected_escalate"],
                "actual": "NOT_FOUND",
                "match": "SKIP",
                "reason": "Transaction not in upload",
            })
            skipped += 1
            continue

        vr = vr_map.get(txn_id)
        if not vr:
            results.append({
                "source_txn_id": src_id,
                "scenario": exp.get("scenario", "?"),
                "expected": exp["expected_escalate"],
                "actual": "NOT_FOUND",
                "match": "SKIP",
                "reason": "No validation result",
            })
            skipped += 1
            continue

        llm_escalated = vr.risk_level == "high"
        expected_val = exp["expected_escalate"]
        match = llm_escalated == expected_val

        if match:
            passed += 1
        else:
            failed += 1

        results.append({
            "source_txn_id": src_id,
            "transaction_id": txn_id,
            "scenario": exp.get("scenario", "?"),
            "expected": expected_val,
            "actual": llm_escalated,
            "match": "PASS" if match else "FAIL",
            "reason": vr.triage_reasoning or "",
        })

    # Print table
    print()
    print(f"{'Scenario':40s} {'Expected':10s} {'Actual':10s} {'Result':6s}  TxnId")
    print("-" * 85)
    for r in results:
        exp_str = "escalate" if r["expected"] else "no_esc "
        act_str = "escalate" if r["actual"] is True else (
            "no_esc " if r["actual"] is False else "NOT_FOUND"
        )
        print(f"{r['scenario']:40s} {exp_str:10s} {act_str:10s} {r['match']:6s}  {r.get('transaction_id', '-'):36s}")
        if r["match"] == "FAIL":
            print(f"  {'':40s} LLM reason: {r['reason']}")

    total = passed + failed
    print()
    print(f"Results: {passed}/{total} passed ({passed / total * 100:.1f}%)" if total else "Results: 0/0")
    if skipped:
        print(f"  Skipped (not found): {skipped}")
    if failed:
        print(f"  Failed: {failed}")
        return 1
    return 0


def run():
    parser = argparse.ArgumentParser(description="Compare LLM triage decisions against .eval expectations")
    parser.add_argument("--upload-id", required=True, help="Upload UUID from the ingestion")
    parser.add_argument("--eval", required=True, type=Path, help="Path to .eval file")
    args = parser.parse_args()

    import asyncio
    return asyncio.run(evaluate(args.upload_id, args.eval))


if __name__ == "__main__":
    sys.exit(run())
