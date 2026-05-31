"""Generate transactions that trigger active deterministic rules in the DB.

Reads all active rules, distributes --count evenly across them, and for each
rule generates a transaction that satisfies its conditions. Appends to --output.
"""

import argparse
import asyncio
import csv
import json
import random
import uuid
from datetime import datetime, UTC, timedelta
from pathlib import Path

from faker import Faker
from sqlalchemy import select

from src.aml_workflow.validator import evaluate_rules
from src.core.models.rule import Rule
from src.bff.database import async_session_factory
from src.file_processor.service import _LOCATION_MAP

# Reverse map: country name → list of CSV location values
_COUNTRY_TO_LOCATIONS: dict[str, list[str]] = {}
for loc, (city, state, country) in _LOCATION_MAP.items():
    _COUNTRY_TO_LOCATIONS.setdefault(country, []).append(loc)

fake = Faker()

MAX_RETRIES = 10


def _expand_location(row: dict) -> dict:
    txn = dict(row)
    loc_raw = txn.pop("location", "")
    entry = _LOCATION_MAP.get(loc_raw)
    if entry:
        txn["city"], txn["state"], txn["country"] = entry
    else:
        txn["city"] = txn["state"] = txn["country"] = ""
    return txn

COUNTERPARTIES = [
    "Acme Corp", "Global Trading", "Refund Co", "Local Shop",
    "Offshore Ltd", "Zero Inc", "Mega Retail", "Payroll Services",
    "Utility Co", "Insurance Plus", "Fast Logistics", "Cloud Host Inc",
    "Consulting Group", "Food Distributors", "Travel Agency",
]

LOCATIONS = [
    "New York", "London", "Chicago", "Boston", "Dallas", "Miami",
    "Seattle", "Denver", "San Francisco", "Los Angeles", "Austin",
    "Atlanta", "Portland", "Phoenix", "Toronto",
]

FIELD_NAMES = ["account_id", "customer_id", "amount", "counterparty", "location", "date", "source_txn_id"]


def _generate_value(field: str, operator: str, value: str | int | float | list) -> str:
    """Generate a value that satisfies the given condition."""
    if operator == ">":
        if field == "amount":
            val = float(value) + random.uniform(1, 100000)
            return f"{val:.2f}"
    elif operator == "<":
        if field == "amount":
            val = float(value) - random.uniform(1, 10000)
            return f"{val:.2f}"
    elif operator == ">=":
        if field == "amount":
            val = float(value) + random.uniform(0, 100000)
            return f"{val:.2f}"
    elif operator == "<=":
        if field == "amount":
            val = float(value) - random.uniform(0, 10000)
            return f"{val:.2f}"
    elif operator == "==":
        return str(value)
    elif operator == "!=":
        return f"{value}_other"
    elif operator == "is_empty":
        return ""
    elif operator == "in":
        if isinstance(value, list) and value:
            return str(random.choice(value))
        return str(value)
    elif operator == "contains":
        return f"{value}_sample"
    return str(value)


def _generate_transaction(
    account_ids: list[str], customer_ids: list[str], date: str,
    conditions: list[dict],
) -> dict:
    txn = {
        "account_id": random.choice(account_ids),
        "customer_id": random.choice(customer_ids),
        "counterparty": random.choice(COUNTERPARTIES),
        "location": random.choice(LOCATIONS),
        "date": date,
        "source_txn_id": f"ST1_{fake.unique.random_number(digits=8)}",
    }
    for cond in conditions:
        field = cond.get("field", "")
        operator = cond.get("operator", "==")
        value = cond.get("value", "")
        val = _generate_value(field, operator, value)
        if field == "country":
            locs = _COUNTRY_TO_LOCATIONS.get(val, [])
            if locs:
                txn["location"] = random.choice(locs)
        else:
            txn[field] = val
    if "amount" not in txn:
        txn["amount"] = f"{random.uniform(1, 1000):.2f}"
    return txn


async def generate(count: int, date: str, output: Path, session=None):
    if session is not None:
        return await _generate(count, date, output, session)
    async with async_session_factory() as s:
        return await _generate(count, date, output, s)


async def _generate(count: int, date: str, output: Path, session):
    result = await session.execute(
        select(Rule).where(Rule.status == "active", Rule.type == "deterministic")
    )
    rules = result.scalars().all()

    if not rules:
        print("ERROR: No active deterministic rules found. Run 'python -m scripts.seed_db' first.")
        return

    rule_dicts = [
        {"id": r.id, "name": r.name, "rules_json": r.rules_json}
        for r in rules
    ]

    from sqlalchemy import text
    acct_result = await session.execute(text("SELECT account_id FROM account"))
    account_ids = [row[0] for row in acct_result.fetchall()]
    cust_result = await session.execute(text("SELECT customer_id FROM customer"))
    customer_ids = [row[0] for row in cust_result.fetchall()]

    if not account_ids or not customer_ids:
        print("ERROR: No customers or accounts found. Run 'python -m scripts.seed_db' first.")
        return

    main_date = date
    prev_date = (datetime.fromisoformat(date) - timedelta(days=1)).strftime("%Y-%m-%d")

    rows: list[dict] = []
    eval_entries: list[dict] = []
    row_counter = 0

    base = count // len(rules)
    extra = count % len(rules)

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
            use_main = random.random() < 0.95
            row_date = main_date if use_main else prev_date

            for attempt in range(MAX_RETRIES + 1):
                txn = _generate_transaction(account_ids, customer_ids, row_date, conditions)
                expanded = _expand_location(txn)
                triggered = evaluate_rules(expanded, rule_dicts)
                if str(rule.id) in triggered or str(rule.name) in triggered.values():
                    break

            rows.append(txn)
            eval_entries.append({
                "source_txn_id": txn["source_txn_id"],
                "scenario": f"STAGE1_{rule.name.upper().replace(' ', '_')}",
                "expected_escalate": True,
                "ground_truth": rule.name,
                "reason_hint": f"Rule-based: {rule.name}",
                "stage": "stage1",
            })

    output_path = Path(output)
    eval_path = output_path.with_suffix(".eval")

    write_header = not output_path.exists()
    with open(output_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

    with open(eval_path, "w") as f:
        for entry in eval_entries:
            f.write(json.dumps(entry) + "\n")

    print(f"Generated {len(rows)} stage-1 fraud transactions -> {output_path}")
    print(f"  Rules: {len(rules)}")
    print(f"  Eval entries: {len(eval_entries)} -> {eval_path}")


async def run():
    parser = argparse.ArgumentParser(description="Generate rule-triggering stage-1 fraud transactions")
    parser.add_argument("--count", type=int, default=1000, help="Number of transactions (default: 1000)")
    parser.add_argument("--date", type=str, default=None,
                        help="Primary transaction date as YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--output", type=str, default="work/upload.csv", help="Output path (default: work/upload.csv)")
    args = parser.parse_args()

    if args.date is None:
        args.date = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")

    await generate(args.count, args.date, Path(args.output))


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
