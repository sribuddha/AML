import argparse
import asyncio
import csv
import random
from datetime import datetime, UTC, timedelta

from faker import Faker
from sqlalchemy import select, text

from src.bff.database import async_session_factory

fake = Faker()

AMOUNT_DISTRIBUTION = [
    (1, 1000, 0.85),
    (1000, 10000, 0.10),
    (10000, 100000, 0.0),
    (-500, -1, 0.03),
    (0, 0, 0.02),
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


def pick_amount(high_value_count: int, total_count: int) -> float:
    """Pick an amount based on distribution, injecting high-value at ~N/50 rate."""
    roll = random.random()
    high_value_threshold = high_value_count / max(total_count, 1)
    if high_value_threshold < 1 and roll < AMOUNT_DISTRIBUTION[2][2]:
        # High-value bucket is filled dynamically
        pass

    for low, high, weight in AMOUNT_DISTRIBUTION:
        if roll <= weight:
            if low == high:
                return float(low)
            return round(random.uniform(low, high), 2)
        roll -= weight

    return round(random.uniform(1, 1000), 2)


def generate_row(
    account_ids: list[str],
    customer_ids: list[str],
    high_value_count: int,
    total_count: int,
) -> dict:
    account_id = random.choice(account_ids)
    customer_id = random.choice(customer_ids)

    amount = pick_amount(high_value_count, total_count)
    if amount >= 10000:
        high_value_count += 1

    return {
        "account_id": account_id,
        "customer_id": customer_id,
        "amount": f"{amount:.2f}",
        "counterparty": random.choice(COUNTERPARTIES),
        "location": random.choice(LOCATIONS),
        "date": fake.date_between(start_date="-2y", end_date="today").isoformat(),
        "source_txn_id": f"SRC{fake.unique.random_number(digits=8)}",
    }, high_value_count


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
        if random.random() < 0.5:
            row["account_id"] = f"INVALID_{fake.unique.random_number(digits=5)}"
        else:
            row["customer_id"] = f"INVALID_{fake.unique.random_number(digits=5)}"

    return row


async def generate(count: int, output: str, bad_rate: float):
    async with async_session_factory() as session:
        result = await session.execute(text("SELECT account_id FROM account"))
        account_ids = [row[0] for row in result.fetchall()]
        result = await session.execute(text("SELECT customer_id FROM customer"))
        customer_ids = [row[0] for row in result.fetchall()]

    if not account_ids or not customer_ids:
        print("ERROR: No customers or accounts found. Run 'python -m scripts.seed_db' first.")
        return

    rows: list[dict] = []
    high_value_count = 0
    high_value_target = max(1, count // 50)

    for i in range(count):
        row, high_value_count = generate_row(account_ids, customer_ids, high_value_count, count)

        if bad_rate > 0 and random.random() < bad_rate:
            row = corrupt_row(row, account_ids, customer_ids)

        rows.append(row)

    def _is_valid_amount(val: str) -> bool:
        try:
            return float(val) >= 0
        except (ValueError, TypeError):
            return False

    def _safe_amount(val: str) -> float:
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    # Ensure at least N/50 high-value rows exist
    actual_high = sum(1 for r in rows if _is_valid_amount(r["amount"]) and float(r["amount"]) >= 10000)
    if actual_high < high_value_target:
        for r in rows:
            if _is_valid_amount(r["amount"]) and float(r["amount"]) < 10000 and actual_high < high_value_target:
                r["amount"] = f"{random.uniform(10000, 100000):.2f}"
                actual_high += 1

    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["account_id", "customer_id", "amount", "counterparty", "location", "date", "source_txn_id"])
        writer.writeheader()
        writer.writerows(rows)

    bad_count = sum(
        1 for r in rows
        if r["amount"] in ("N/A", "unknown", "free", "")
        or r["date"] in ("not-a-date", "13-32-2026", "Feb 30", "")
        or r.get("account_id", "").startswith("INVALID_")
        or r.get("customer_id", "").startswith("INVALID_")
        or not r.get("counterparty", "")
        or not r.get("location", "")
    )

    valid_amounts = [_safe_amount(r["amount"]) for r in rows if _is_valid_amount(r["amount"])]
    amount_min = min(valid_amounts) if valid_amounts else 0
    amount_max = max(valid_amounts) if valid_amounts else 0

    print(f"Generated {count} transactions -> {output}")
    print(f"  Valid rows:     {count - bad_count}")
    print(f"  Bad rows:       {bad_count} ({bad_rate*100:.1f}% rate)")
    print(f"  High-value:     {actual_high} (target: >={high_value_target})")
    print(f"  Amount range:   ${amount_min:.2f} - ${amount_max:.2f}")


def main():
    parser = argparse.ArgumentParser(description="Generate sample CSV transaction file")
    parser.add_argument("--count", type=int, default=1000, help="Number of transactions (default: 1000)")
    parser.add_argument("--output", type=str, default="data/sample_transactions.csv", help="Output path (default: data/sample_transactions.csv)")
    parser.add_argument("--bad-rate", type=float, default=0.0, help="Fraction of rows with intentionally bad data (0.0–1.0, default: 0.0)")
    args = parser.parse_args()

    if args.bad_rate < 0 or args.bad_rate > 1:
        parser.error("--bad-rate must be between 0.0 and 1.0")

    asyncio.run(generate(args.count, args.output, args.bad_rate))


if __name__ == "__main__":
    main()
