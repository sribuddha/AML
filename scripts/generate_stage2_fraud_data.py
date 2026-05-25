"""Generate scenario-based transactions for LLM triage evaluation.

Each transaction targets a specific triage scenario to test whether the LLM
makes the correct escalation decision. Appends to --output CSV and its .eval
companion (JSONL)."""

import argparse
import asyncio
import csv
import json
import random
import uuid
from datetime import datetime, UTC, timedelta
from pathlib import Path

from faker import Faker
from sqlalchemy import text

from src.bff.database import async_session_factory

fake = Faker()

FIELD_NAMES = [
    "account_id", "customer_id", "amount", "counterparty",
    "location", "date", "source_txn_id",
]

SCENARIOS: list[dict] = [
    # (tag, scenario_name, params, expected_escalate, ground_truth_label, reason_hint)
    {
        "tag": "GEO_OFFSHORE",
        "scenario": "Geo + Offshore",
        "amount": 9500.0, "counterparty": "Offshore Ltd",
        "location": "Iran",
        "expected_escalate": True,
        "ground_truth": "escalate_geo_offshore",
        "reason_hint": "Iran + Offshore Ltd",
    },
    {
        "tag": "STRUCTURING",
        "scenario": "Structuring",
        "amount": 9800.0, "counterparty": "Local Shop",
        "location": "Miami",
        "expected_escalate": True,
        "ground_truth": "escalate_structuring",
        "reason_hint": "near threshold + round amount",
    },
    {
        "tag": "HIGH_VALUE",
        "scenario": "High value only",
        "amount": 55000.0, "counterparty": "Acme Corp",
        "location": "London",
        "expected_escalate": True,
        "ground_truth": "escalate_high_value",
        "reason_hint": "amount exceeds $50K",
    },
    {
        "tag": "GEO_ONLY",
        "scenario": "Geo only",
        "amount": 200.0, "counterparty": "Local Shop",
        "location": "North Korea",
        "expected_escalate": True,
        "ground_truth": "escalate_geo_only",
        "reason_hint": "high-risk jurisdiction alone",
    },
    {
        "tag": "MULTI_LOW",
        "scenario": "Multiple low signals",
        "amount": 7500.0, "counterparty": "Offshore Ltd",
        "location": "London",
        "expected_escalate": True,
        "ground_truth": "escalate_multi_low",
        "reason_hint": "offshore + moderate amount",
    },
    {
        "tag": "THRESHOLD_ONLY",
        "scenario": "Threshold only",
        "amount": 8500.0, "counterparty": "Local Shop",
        "location": "Boston",
        "expected_escalate": False,
        "ground_truth": "no_escalate_threshold",
        "reason_hint": "single low-severity flag",
    },
    {
        "tag": "ROUND_ONLY",
        "scenario": "Round amount only",
        "amount": 5000.0, "counterparty": "Utility Co",
        "location": "Chicago",
        "expected_escalate": False,
        "ground_truth": "no_escalate_round",
        "reason_hint": "single low-severity flag",
    },
    {
        "tag": "LOW_OFFSHORE",
        "scenario": "Small + offshore",
        "amount": 3000.0, "counterparty": "Offshore Ltd",
        "location": "London",
        "expected_escalate": False,
        "ground_truth": "no_escalate_low_offshore",
        "reason_hint": "low amount with offshore but no corroborating signals",
    },
    {
        "tag": "NEGATIVE",
        "scenario": "Negative amount",
        "amount": -100.0, "counterparty": "Refund Co",
        "location": "Boston",
        "expected_escalate": True,
        "ground_truth": "escalate_negative",
        "reason_hint": "anomalous negative amount",
    },
]


def _generate_row(scenario: dict, date: str, index: int,
                  account_ids: list[str], customer_ids: list[str]) -> dict:
    src_id = f"ST2_{scenario['tag']}_{index:03d}"
    return {
        "account_id": random.choice(account_ids),
        "customer_id": random.choice(customer_ids),
        "amount": f"{scenario['amount']:.2f}",
        "counterparty": scenario["counterparty"],
        "location": scenario["location"],
        "date": date,
        "source_txn_id": src_id,
    }


def _eval_entry(scenario: dict, date: str, index: int) -> dict:
    return {
        "source_txn_id": f"ST2_{scenario['tag']}_{index:03d}",
        "scenario": scenario["scenario"],
        "expected_escalate": scenario["expected_escalate"],
        "ground_truth": scenario["ground_truth"],
        "reason_hint": scenario["reason_hint"],
    }


async def generate(count: int, date: str, output: Path):
    async with async_session_factory() as session:
        acct_result = await session.execute(text("SELECT account_id FROM account"))
        account_ids = [row[0] for row in acct_result.fetchall()]
        cust_result = await session.execute(text("SELECT customer_id FROM customer"))
        customer_ids = [row[0] for row in cust_result.fetchall()]

    if not account_ids or not customer_ids:
        print("ERROR: No customers or accounts found. Run 'python -m scripts.seed_db' first.")
        return

    output_path = Path(output)
    eval_path = output_path.with_suffix(".eval")

    scenarios = SCENARIOS
    rows: list[dict] = []
    eval_entries: list[dict] = []

    base = count // len(scenarios)
    extra = count % len(scenarios)

    for i, scenario in enumerate(scenarios):
        batch = base + (1 if i < extra else 0)
        if batch == 0:
            continue
        for j in range(batch):
            idx = i * base + j + 1
            row_date = date if random.random() < 0.95 else (
                datetime.fromisoformat(date) - timedelta(days=1)
            ).strftime("%Y-%m-%d")
            rows.append(_generate_row(scenario, row_date, idx, account_ids, customer_ids))
            eval_entries.append(_eval_entry(scenario, row_date, idx))

    write_header = not output_path.exists()
    with open(output_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

    with open(eval_path, "a") as f:
        for entry in eval_entries:
            f.write(json.dumps(entry) + "\n")

    print(f"Generated {len(rows)} stage-2 fraud transactions -> {output_path}")
    print(f"Appended {len(eval_entries)} eval entries -> {eval_path}")
    print(f"  Scenarios: {len(scenarios)}, Exact count: {len(rows)}")


def run():
    parser = argparse.ArgumentParser(
        description="Generate scenario-based stage-2 fraud transactions for LLM triage eval"
    )
    parser.add_argument("--count", type=int, default=20,
                        help="Number of transactions (default: 20)")
    parser.add_argument("--date", type=str, default=None,
                        help="Primary transaction date as YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--output", type=str, default="work/upload.csv",
                        help="Output path (default: work/upload.csv)")
    args = parser.parse_args()

    if args.date is None:
        args.date = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")

    generate(args.count, args.date, Path(args.output))


if __name__ == "__main__":
    run()
