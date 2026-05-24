"""Generate a CSV of transactions for upload, with configurable bad rows and date distribution.

95% of records use the specified --date, 5% use the day before.
Appends to --output (writes header only if file doesn't exist).
"""

import argparse
import asyncio
import csv
import random
import uuid
from datetime import datetime, UTC, timedelta
from pathlib import Path

from faker import Faker
from sqlalchemy import text

from src.bff.database import async_session_factory

fake = Faker()

AMOUNT_DISTRIBUTION = [
    (1, 1000, 0.85),
    (1000, 10000, 0.10),
    (10000, 100000, 0.05),
]

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


def pick_amount() -> float:
    roll = random.random()
    for low, high, weight in AMOUNT_DISTRIBUTION:
        if roll <= weight:
            return round(random.uniform(low, high), 2)
        roll -= weight
    return round(random.uniform(1, 1000), 2)


def generate_row(account_ids: list[str], customer_ids: list[str], date: str) -> dict:
    return {
        "account_id": random.choice(account_ids),
        "customer_id": random.choice(customer_ids),
        "amount": f"{pick_amount():.2f}",
        "counterparty": random.choice(COUNTERPARTIES),
        "location": random.choice(LOCATIONS),
        "date": date,
        "source_txn_id": f"SRC{fake.unique.random_number(digits=8)}",
    }


def corrupt_row(row: dict, account_ids: list[str], customer_ids: list[str]) -> dict:
    corruption = random.choice(["missing_field", "bad_amount", "bad_date", "bad_fk"])
    row = dict(row)

    if corruption == "missing_field":
        field = random.choice(["counterparty", "location", "amount"])
        row[field] = ""
    elif corruption == "bad_amount":
        row["amount"] = random.choice(["N/A", "unknown", "free", ""])
    elif corruption == "bad_date":
        row["date"] = random.choice(["not-a-date", "13-32-2026", "Feb 30", ""])
    elif corruption == "bad_fk":
        row["account_id"] = f"INVALID_{fake.unique.random_number(digits=5)}"

    return row


async def generate(count: int, bad_rate: int, date: str, output: Path, session=None):
    if session is None:
        async with async_session_factory() as s:
            return await _generate(count, bad_rate, date, output, s)
    else:
        return await _generate(count, bad_rate, date, output, session)


async def _generate(count: int, bad_rate: int, date: str, output: Path, session):
    result = await session.execute(text("SELECT account_id FROM account"))
    account_ids = [row[0] for row in result.fetchall()]
    result = await session.execute(text("SELECT customer_id FROM customer"))
    customer_ids = [row[0] for row in result.fetchall()]

    if not account_ids or not customer_ids:
        print("ERROR: No customers or accounts found. Run 'python -m scripts.seed_db' first.")
        return

    main_date = date
    prev_date = (datetime.fromisoformat(date) - timedelta(days=1)).strftime("%Y-%m-%d")

    rows: list[dict] = []
    for i in range(count):
        use_main = random.random() < 0.95
        row_date = main_date if use_main else prev_date
        row = generate_row(account_ids, customer_ids, row_date)

        if bad_rate > 0 and i < bad_rate:
            row = corrupt_row(row, account_ids, customer_ids)

        rows.append(row)

    write_header = not output.exists()
    with open(output, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

    bad_count = sum(
        1 for r in rows
        if r["amount"] in ("N/A", "unknown", "free", "")
        or r["date"] in ("not-a-date", "13-32-2026", "Feb 30", "")
        or r.get("account_id", "").startswith("INVALID_")
        or not r.get("counterparty", "")
        or not r.get("location", "")
    )

    print(f"Generated {count} transactions -> {output}")
    print(f"  Valid rows:         {count - bad_count}")
    print(f"  Bad rows:           {bad_count}")
    print(f"  Main date ({main_date}): {sum(1 for r in rows if r['date'] == main_date)}")
    print(f"  Prev date ({prev_date}): {sum(1 for r in rows if r['date'] == prev_date)}")


async def run():
    parser = argparse.ArgumentParser(description="Generate upload-ready CSV transaction file")
    parser.add_argument("--count", type=int, default=1000, help="Number of transactions (default: 1000)")
    parser.add_argument("--bad-rate", type=int, default=0, help="Number of intentionally bad rows (default: 0)")
    parser.add_argument("--date", type=str, default=None,
                        help="Primary transaction date as YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--output", type=str, default="work/upload.csv", help="Output path (default: work/upload.csv)")
    args = parser.parse_args()

    if args.date is None:
        args.date = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")

    if args.bad_rate < 0 or args.bad_rate > args.count:
        parser.error("--bad-rate must be between 0 and --count")

    await generate(args.count, args.bad_rate, args.date, Path(args.output))


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
