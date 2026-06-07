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
        "scenario": "STAGE2_GEO_OFFSHORE",
        "amount": 9500.0, "counterparty": "Offshore Ltd",
        "location": "Iran",
        "expected_escalate": True,
        "ground_truth": "escalate_geo_offshore",
        "reason_hint": "Iran + Offshore Ltd",
    },
    {
        "tag": "STRUCTURING",
        "scenario": "STAGE2_STRUCTURING",
        "amount": 9800.0, "counterparty": "Local Shop",
        "location": "Miami",
        "expected_escalate": True,
        "ground_truth": "escalate_structuring",
        "reason_hint": "near threshold + round amount",
    },
    {
        "tag": "HIGH_VALUE",
        "scenario": "STAGE2_HIGH_VALUE",
        "amount": 55000.0, "counterparty": "Acme Corp",
        "location": "London",
        "expected_escalate": True,
        "ground_truth": "escalate_high_value",
        "reason_hint": "amount exceeds $50K",
    },
    {
        "tag": "GEO_ONLY",
        "scenario": "STAGE2_GEO_ONLY",
        "amount": 200.0, "counterparty": "Local Shop",
        "location": "North Korea",
        "expected_escalate": True,
        "ground_truth": "escalate_geo_only",
        "reason_hint": "high-risk jurisdiction alone",
    },
    {
        "tag": "MULTI_LOW",
        "scenario": "STAGE2_MULTI_LOW",
        "amount": 7500.0, "counterparty": "Offshore Ltd",
        "location": "London",
        "expected_escalate": True,
        "ground_truth": "escalate_multi_low",
        "reason_hint": "offshore + moderate amount",
    },
    {
        "tag": "THRESHOLD_ONLY",
        "scenario": "STAGE2_THRESHOLD_ONLY",
        "amount": 8500.0, "counterparty": "Local Shop",
        "location": "Boston",
        "expected_escalate": True,
        "ground_truth": "escalate_threshold",
        "reason_hint": "flagged by threshold proximity rule",
    },
    {
        "tag": "ROUND_ONLY",
        "scenario": "STAGE2_ROUND_ONLY",
        "amount": 5000.0, "counterparty": "Utility Co",
        "location": "Chicago",
        "expected_escalate": True,
        "ground_truth": "escalate_round",
        "reason_hint": "flagged by round amount rule",
    },
    {
        "tag": "LOW_OFFSHORE",
        "scenario": "STAGE2_LOW_OFFSHORE",
        "amount": 3000.0, "counterparty": "Offshore Ltd",
        "location": "London",
        "expected_escalate": True,
        "ground_truth": "escalate_low_offshore",
        "reason_hint": "flagged by offshore counterparty rule",
    },
    {
        "tag": "NEGATIVE",
        "scenario": "STAGE2_NEGATIVE",
        "amount": -100.0, "counterparty": "Refund Co",
        "location": "Boston",
        "expected_escalate": True,
        "ground_truth": "escalate_negative",
        "reason_hint": "anomalous negative amount",
    },
]

CLEARABLE_TEMPLATES: list[dict] = [
    {
        "tag": "CLEARABLE_THRESHOLD",
        "scenario": "CLEARABLE_THRESHOLD",
        "amount": 9500.0, "counterparty": "Local Shop",
        "location": "Chicago",
        "expected_escalate": False,
        "expected_auto_reviewed": True,
        "ground_truth": "auto_review_threshold",
        "reason_hint": "flagged by threshold proximity but domestic & benign",
    },
    {
        "tag": "CLEARABLE_ROUND",
        "scenario": "CLEARABLE_ROUND",
        "amount": 5000.0, "counterparty": "Payroll Services",
        "location": "Austin",
        "expected_escalate": False,
        "expected_auto_reviewed": True,
        "ground_truth": "auto_review_round",
        "reason_hint": "flagged by round amount but payroll payment",
    },
    {
        "tag": "CLEARABLE_NEGATIVE",
        "scenario": "CLEARABLE_NEGATIVE",
        "amount": -75.0, "counterparty": "Refund Co",
        "location": "Boston",
        "expected_escalate": False,
        "expected_auto_reviewed": True,
        "ground_truth": "auto_review_negative",
        "reason_hint": "flagged by negative amount but small refund",
    },
]


def _generate_row(scenario: dict, date: str, index: int,
                  account_ids: list[str], customer_ids: list[str],
                  *, prefix: str = "ST2") -> dict:
    src_id = f"{prefix}_{scenario['tag']}_{index:03d}"
    return {
        "account_id": random.choice(account_ids),
        "customer_id": random.choice(customer_ids),
        "amount": f"{scenario['amount']:.2f}",
        "counterparty": scenario["counterparty"],
        "location": scenario["location"],
        "date": date,
        "source_txn_id": src_id,
    }


def _eval_entry(scenario: dict, date: str, index: int, prefix: str = "ST2") -> dict:
    entry: dict = {
        "source_txn_id": f"{prefix}_{scenario['tag']}_{index:03d}",
        "scenario": scenario["scenario"],
        "expected_escalate": scenario["expected_escalate"],
        "ground_truth": scenario["ground_truth"],
        "reason_hint": scenario["reason_hint"],
        "stage": "stage2",
    }
    if scenario.get("expected_auto_reviewed"):
        entry["expected_auto_reviewed"] = True
    return entry


async def generate(count: int, date: str, output: Path, *, auto_review_count: int = 0):
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

    auto_review_rows: list[dict] = []
    auto_review_eval: list[dict] = []
    for k in range(auto_review_count):
        tmpl = random.choice(CLEARABLE_TEMPLATES)
        row_date = date if random.random() < 0.95 else (
            datetime.fromisoformat(date) - timedelta(days=1)
        ).strftime("%Y-%m-%d")
        src_id = f"AR_{tmpl['tag']}_{k:03d}"
        row = {
            "account_id": random.choice(account_ids),
            "customer_id": random.choice(customer_ids),
            "amount": f"{tmpl['amount']:.2f}",
            "counterparty": tmpl["counterparty"],
            "location": tmpl["location"],
            "date": row_date,
            "source_txn_id": src_id,
        }
        auto_review_rows.append(row)
        eval_entry: dict = {
            "source_txn_id": src_id,
            "scenario": tmpl["scenario"],
            "expected_escalate": tmpl["expected_escalate"],
            "expected_auto_reviewed": True,
            "ground_truth": tmpl["ground_truth"],
            "reason_hint": tmpl["reason_hint"],
            "stage": "stage2",
        }
        auto_review_eval.append(eval_entry)

    all_rows = rows + auto_review_rows
    all_eval = eval_entries + auto_review_eval

    write_header = not output_path.exists()
    with open(output_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(all_rows)

    with open(eval_path, "a") as f:
        for entry in all_eval:
            f.write(json.dumps(entry) + "\n")

    print(f"Generated {len(all_rows)} stage-2 fraud transactions -> {output_path}")
    print(f"  Scenarios: {len(rows)} (across {len(scenarios)} types)")
    if auto_review_count:
        print(f"  Auto-review targets: {auto_review_count}")
    print(f"Appended {len(all_eval)} eval entries -> {eval_path}")


def run():
    parser = argparse.ArgumentParser(
        description="Generate scenario-based stage-2 fraud transactions for LLM triage eval"
    )
    parser.add_argument("--count", type=int, default=20,
                        help="Number of transactions (default: 20)")
    parser.add_argument("--auto-review-count", type=int, default=0,
                        help="Additional transactions guaranteed to be auto-reviewed target (default: 0)")
    parser.add_argument("--date", type=str, default=None,
                        help="Primary transaction date as YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--output", type=str, default="work/upload.csv",
                        help="Output path (default: work/upload.csv)")
    args = parser.parse_args()

    if args.date is None:
        args.date = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")

    generate(args.count, args.date, Path(args.output),
             auto_review_count=args.auto_review_count)


if __name__ == "__main__":
    run()
