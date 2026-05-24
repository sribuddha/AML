"""Generate a triage test dataset, upload it, and run the workflow.

Usage:
    python -m scripts.generate_triage_dataset --count 300 --clean-count 100 --days 60
    python -m scripts.generate_triage_dataset --count 300 --triage-only
"""

import argparse
import asyncio
import csv
import json
import math
import random
import uuid
from datetime import datetime, timedelta, UTC
from io import BytesIO
from pathlib import Path

import pandas as pd
from faker import Faker
from sqlalchemy import select, text

from src.aml_workflow.models.rule import Rule
from src.aml_workflow.models.validation_result import ValidationResult
from src.aml_workflow.models.sar import SAR
from src.aml_workflow.models.enrichment_snapshot import EnrichmentSnapshot
from src.file_processor.models import Transaction
from src.bff.database import async_session_factory
from src.file_processor.service import process_upload
from src.aml_workflow.triggers import run_validation
from src.aml_workflow.llm import LLMClient

fake = Faker()

COUNTERPARTIES = [
    "Acme Corp", "Global Trading", "Refund Co", "Local Shop",
    "Offshore Ltd", "Zero Inc", "Mega Retail", "Payroll Services",
    "Utility Co", "Insurance Plus", "Fast Logistics", "Cloud Host Inc",
    "Consulting Group", "Food Distributors", "Travel Agency",
]

CLEAN_COUNTERPARTIES = [
    "Acme Corp", "Global Trading", "Refund Co", "Local Shop",
    "Zero Inc", "Mega Retail", "Payroll Services",
    "Utility Co", "Insurance Plus", "Fast Logistics", "Cloud Host Inc",
    "Consulting Group", "Food Distributors", "Travel Agency",
]

ROUND_AMOUNTS = {1000, 5000, 10000, 20000, 50000}

LOCATIONS = [
    "New York", "London", "Chicago", "Boston", "Dallas", "Miami",
    "Seattle", "Denver", "San Francisco", "Los Angeles", "Austin",
    "Atlanta", "Portland", "Phoenix", "Toronto",
]

FIELD_NAMES = ["account_id", "customer_id", "amount", "counterparty", "location", "date", "source_txn_id"]


def _generate_value(field: str, operator: str, value: str | int | float | list) -> str:
    if operator == ">":
        if field == "amount":
            return f"{float(value) + random.uniform(1, 100000):.2f}"
    elif operator == "<":
        if field == "amount":
            return f"{float(value) - random.uniform(1, 10000):.2f}"
    elif operator == ">=":
        if field == "amount":
            return f"{float(value) + random.uniform(0, 100000):.2f}"
    elif operator == "<=":
        if field == "amount":
            return f"{float(value) - random.uniform(0, 10000):.2f}"
    elif operator == "==":
        return str(value)
    elif operator == "!=":
        return f"{value}_other"
    elif operator == "is_empty":
        return ""
    elif operator == "in":
        return str(random.choice(value)) if isinstance(value, list) else str(value)
    elif operator == "contains":
        return f"{value}_sample"
    return str(value)


def _generate_fraud_txn(account_ids: list[str], customer_ids: list[str], date: str, conditions: list[dict]) -> dict:
    txn = {
        "account_id": random.choice(account_ids),
        "customer_id": random.choice(customer_ids),
        "counterparty": random.choice(COUNTERPARTIES),
        "location": random.choice(LOCATIONS),
        "date": date,
        "source_txn_id": f"TRIAGE_{fake.unique.random_number(digits=8)}",
    }
    for cond in conditions:
        field = cond.get("field", "")
        operator = cond.get("operator", "==")
        value = cond.get("value", "")
        txn[field] = _generate_value(field, operator, value)
    if "amount" not in txn:
        txn["amount"] = f"{random.uniform(1, 1000):.2f}"
    return txn


def _generate_clean_txn(account_ids: list[str], customer_ids: list[str], date: str) -> dict:
    amount = round(random.uniform(1, 5000), 2)
    while amount in ROUND_AMOUNTS:
        amount = round(random.uniform(1, 5000), 2)
    return {
        "account_id": random.choice(account_ids),
        "customer_id": random.choice(customer_ids),
        "amount": f"{amount:.2f}",
        "counterparty": random.choice(CLEAN_COUNTERPARTIES),
        "location": random.choice(LOCATIONS),
        "date": date,
        "source_txn_id": f"CLEAN_{fake.unique.random_number(digits=8)}",
    }


async def generate(args) -> Path:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Rule).where(Rule.status == "active", Rule.type == "deterministic")
        )
        rules = result.scalars().all()
        if not rules:
            raise RuntimeError("No active deterministic rules found. Run 'python -m scripts.seed_db' first.")

        acct_result = await session.execute(text("SELECT account_id FROM account"))
        all_account_ids = [row[0] for row in acct_result.fetchall()]
        cust_result = await session.execute(text("SELECT customer_id FROM customer"))
        all_customer_ids = [row[0] for row in cust_result.fetchall()]

        if not all_account_ids or not all_customer_ids:
            raise RuntimeError("No customers or accounts found. Run 'python -m scripts.seed_db' first.")

        target_cust_ids = args.customers.split(",")
        for c in target_cust_ids:
            if c not in all_customer_ids:
                raise RuntimeError(f"Customer {c} not found in DB. Run 'python -m scripts.seed_db --force'.")

        placeholders = ",".join(f"'{c}'" for c in target_cust_ids)
        acct_result_focus = await session.execute(
            text(f"SELECT account_id FROM account WHERE customer_id IN ({placeholders})"),
        )
        target_account_ids = [row[0] for row in acct_result_focus.fetchall()]
        if not target_account_ids:
            raise RuntimeError(f"No accounts found for customers {args.customers}.")

    fraud_count = args.count - args.clean_count
    if fraud_count <= 0:
        raise RuntimeError("clean-count must be less than count.")

    base_date = datetime.now(UTC)

    rows: list[dict] = []
    eval_entries: list[dict] = []

    base = fraud_count // len(rules)
    extra = fraud_count % len(rules)
    row_counter = 0

    for i, rule in enumerate(rules):
        batch = base + (1 if i < extra else 0)
        if batch == 0:
            continue
        conditions = []
        try:
            parsed = json.loads(rule.rules_json)
            conditions = parsed if isinstance(parsed, list) else [parsed]
        except (json.JSONDecodeError, TypeError):
            pass

        for _ in range(batch):
            row_counter += 1
            row_date = (base_date - timedelta(days=random.randint(0, args.days))).strftime("%Y-%m-%d")
            txn = _generate_fraud_txn(target_account_ids, target_cust_ids, row_date, conditions)
            rows.append(txn)
            eval_entries.append({
                "source_txn_id": txn["source_txn_id"],
                "scenario": f"STAGE1_{rule.name.upper().replace(' ', '_')}",
                "expected_escalate": True,
                "ground_truth": rule.name,
                "reason_hint": f"Triggers rule: {rule.name}",
            })

    for _ in range(args.clean_count):
        row_date = (base_date - timedelta(days=random.randint(0, args.days))).strftime("%Y-%m-%d")
        txn = _generate_clean_txn(all_account_ids, all_customer_ids, row_date)
        rows.append(txn)

    random.shuffle(rows)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES)
        writer.writeheader()
        writer.writerows(rows)

    eval_path = output_path.with_suffix(".eval")
    with open(eval_path, "w") as f:
        for entry in eval_entries:
            f.write(json.dumps(entry) + "\n")

    print(f"Generated {len(rows)} transactions -> {output_path}")
    print(f"  Clean: {args.clean_count}, Fraud: {fraud_count} across {len(rules)} rules")
    print(f"  Fraud customers: {args.customers}")
    print(f"  Date window: {args.days} days")
    print(f"  Eval entries: {len(eval_entries)} -> {eval_path}")

    return output_path


async def upload_csv(session, csv_path: Path) -> str:
    content = csv_path.read_bytes()
    df = pd.read_csv(BytesIO(content))

    from src.file_processor.service import HEADER_ALIASES, REQUIRED_FIELDS
    col_map = {}
    for col in df.columns:
        stripped = col.strip().lower()
        for canonical, aliases in HEADER_ALIASES.items():
            if stripped in aliases:
                col_map[col] = canonical
                break
    df = df.rename(columns=col_map)
    keep_cols = list(REQUIRED_FIELDS)
    if "source_txn_id" in df.columns:
        keep_cols.append("source_txn_id")
    df = df[keep_cols]

    upload_id = str(uuid.uuid4())
    result = await process_upload(df, csv_path.name, upload_id, session, content)
    return result["upload_id"]


async def report(session, upload_id: str, mode: str, eval_path: Path):
    txn_result = await session.execute(
        select(Transaction).where(Transaction.upload_id == upload_id)
    )
    txns = txn_result.scalars().all()

    vr_result = await session.execute(
        select(ValidationResult).where(ValidationResult.upload_id == upload_id)
    )
    vrs = vr_result.scalars().all()

    sar_result = await session.execute(
        select(SAR).where(SAR.upload_id == upload_id)
    )
    sars = sar_result.scalars().all()

    snap_result = await session.execute(
        select(EnrichmentSnapshot).where(EnrichmentSnapshot.upload_id == upload_id)
    )
    snaps = snap_result.scalars().all()

    flagged = sum(1 for v in vrs if v.status == "flagged")
    escalated = sum(1 for v in vrs if v.risk_level == "high")
    auto_reviewed = sum(1 for v in vrs if v.risk_level == "auto_reviewed")
    no_risk = sum(1 for v in vrs if v.risk_level is None)

    from collections import Counter
    rule_counts: Counter[str] = Counter()
    for v in vrs:
        if v.flag_details:
            for rule_name in v.flag_details.values():
                rule_counts[rule_name] += 1

    print()
    print("=== Triage Test Report ===")
    print(f"  Upload ID:           {upload_id}")
    print(f"  Mode:                {mode}")
    print(f"  Total transactions:  {len(txns)}")
    print(f"  Validation results:  {len(vrs)}")
    print(f"    Flagged:           {flagged}")
    print(f"    Escalated (high):  {escalated}")
    print(f"    Auto-reviewed:     {auto_reviewed}")
    if no_risk:
        print(f"    No risk_level:     {no_risk}")
    print(f"  Enrichment snapshots: {len(snaps)} customers")
    print(f"  SARs created:        {len(sars)}")

    from src.file_processor.models import UploadedFiles
    upload_rec = await session.get(UploadedFiles, upload_id)
    if upload_rec:
        print(f"  Upload status:       {upload_rec.status}")
    print(f"  .eval file:          {eval_path}")

    if rule_counts:
        print()
        print("  Rule coverage:")
        for rule_name, count in sorted(rule_counts.items()):
            print(f"    {rule_name:30s} {count} flagged")

    print()


async def run(args):
    csv_path = await generate(args)

    if args.generate_only:
        print(f"Upload manually via: curl -X POST http://localhost:8000/api/uploads -F \"file=@{csv_path}\"")
        return

    mode = "stage3" if args.triage_only else "full"

    async with async_session_factory() as session:
        upload_id = await upload_csv(session, csv_path)
        print(f"Uploaded: {upload_id}")

        llm = LLMClient()
        try:
            await run_validation(upload_id, session, llm=llm, mode=mode)
        except Exception as e:
            print(f"Workflow failed: {e}")
            raise

    async with async_session_factory() as session:
        await report(session, upload_id, mode, csv_path.with_suffix(".eval"))


def main():
    parser = argparse.ArgumentParser(
        description="Generate triage test dataset, upload, and run the workflow"
    )
    parser.add_argument("--count", type=int, default=300, help="Total transactions (default: 300)")
    parser.add_argument("--clean-count", type=int, default=100, help="Transactions that trigger no rule (default: 100)")
    parser.add_argument("--customers", type=str, default="CUST001,CUST002,CUST003",
                        help="Comma-separated customer IDs for fraud transactions (default: CUST001,CUST002,CUST003)")
    parser.add_argument("--days", type=int, default=60, help="Date spread window in days (default: 60)")
    parser.add_argument("--output", type=str, default="work/triage.csv", help="Output CSV path (default: work/triage.csv)")
    parser.add_argument("--triage-only", action="store_true", help="Stop after triage (stage3 mode, no real SAR generation)")
    parser.add_argument("--generate-only", action="store_true", help="Only generate CSV, skip upload and workflow")
    args = parser.parse_args()

    if args.clean_count >= args.count:
        parser.error("clean-count must be less than count.")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
