"""Generate synthetic fraud pattern dataset for eval harness.

Creates a CSV with ~10,000 clean transactions and ~200 anomalous ones
across 5 fraud patterns, each labeled with ground_truth.
Also outputs a JSON manifest mapping source_txn_id → pattern label.
"""

import argparse
import asyncio
import json
import random
import uuid as _uuid
from datetime import datetime, UTC, timedelta
from pathlib import Path

from faker import Faker
from sqlalchemy import text

from src.bff.database import async_session_factory

fake = Faker()

COUNTERPARTIES = [
    "Acme Corp", "Global Trading", "Refund Co", "Local Shop",
    "Offshore Ltd", "Mega Retail", "Payroll Services",
    "Utility Co", "Insurance Plus", "Fast Logistics", "Cloud Host Inc",
    "Consulting Group", "Food Distributors", "Travel Agency",
]

LOCATIONS = [
    "New York", "London", "Chicago", "Boston", "Dallas", "Miami",
    "Seattle", "Denver", "San Francisco", "Los Angeles", "Austin",
    "Atlanta", "Portland", "Phoenix", "Toronto", "Lagos", "Dubai",
]

WATCHLIST_COUNTERPARTIES = ["OFAC_Sanctions_Ltd", "North_Korea_Trading_Co", "Iran_Petrochem"]


def _gen_txn_id():
    return f"FRAUD_{fake.unique.random_number(digits=8)}"


def _clean_row(account_id, customer_id, txn_id, days_ago):
    return {
        "account_id": account_id,
        "customer_id": customer_id,
        "amount": f"{round(random.uniform(1, 5000), 2):.2f}",
        "counterparty": random.choice(COUNTERPARTIES),
        "location": random.choice(LOCATIONS),
        "date": (datetime.now(UTC) - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
        "source_txn_id": txn_id,
    }


# ── Pattern generators ──────────────────────────────────────────────

def generate_structuring_set(account_id, customer_id, start_days_ago):
    """Generate 3-5 deposits just under $10k within 24h."""
    count = random.randint(3, 5)
    rows = []
    base_date = datetime.now(UTC) - timedelta(days=start_days_ago)
    for i in range(count):
        amount = round(random.uniform(9500, 9990), 2)
        rows.append({
            "account_id": account_id,
            "customer_id": customer_id,
            "amount": f"{amount:.2f}",
            "counterparty": random.choice(COUNTERPARTIES),
            "location": random.choice(LOCATIONS),
            "date": (base_date + timedelta(hours=random.randint(0, 20))).strftime("%Y-%m-%d"),
            "source_txn_id": _gen_txn_id(),
            "ground_truth": "structuring",
        })
    return rows


def generate_velocity_set(account_id, customer_id, start_days_ago):
    """Account dormant 90+ days then 5+ transactions in 48h."""
    rows = []
    # 5-8 transactions in 48h after dormancy
    count = random.randint(5, 8)
    base_date = datetime.now(UTC) - timedelta(days=start_days_ago)
    for i in range(count):
        amount = round(random.uniform(1000, 15000), 2)
        rows.append({
            "account_id": account_id,
            "customer_id": customer_id,
            "amount": f"{amount:.2f}",
            "counterparty": random.choice(COUNTERPARTIES),
            "location": random.choice(LOCATIONS),
            "date": (base_date + timedelta(hours=random.randint(0, 48))).strftime("%Y-%m-%d"),
            "source_txn_id": _gen_txn_id(),
            "ground_truth": "velocity",
        })
    return rows


def generate_impossible_travel_pair(account_id, customer_id, start_days_ago):
    """Two transactions from distant cities within <2h."""
    base_date = datetime.now(UTC) - timedelta(days=start_days_ago)
    pairs = [
        ("New York", "London"),
        ("Los Angeles", "Tokyo"),
        ("Chicago", "Dubai"),
        ("Boston", "Lagos"),
        ("San Francisco", "Singapore"),
    ]
    loc1, loc2 = random.choice(pairs)
    return [
        {
            "account_id": account_id,
            "customer_id": customer_id,
            "amount": f"{round(random.uniform(5000, 25000), 2):.2f}",
            "counterparty": random.choice(COUNTERPARTIES),
            "location": loc1,
            "date": base_date.strftime("%Y-%m-%d"),
            "source_txn_id": _gen_txn_id(),
            "ground_truth": "impossible_travel",
        },
        {
            "account_id": account_id,
            "customer_id": customer_id,
            "amount": f"{round(random.uniform(5000, 25000), 2):.2f}",
            "counterparty": random.choice(COUNTERPARTIES),
            "location": loc2,
            "date": (base_date + timedelta(hours=1, minutes=random.randint(0, 45))).strftime("%Y-%m-%d"),
            "source_txn_id": _gen_txn_id(),
            "ground_truth": "impossible_travel",
        },
    ]


def generate_round_trip_pair(account_id, customer_id, start_days_ago):
    """Outbound then inbound from same counterparty within 72h."""
    base_amount = round(random.uniform(10000, 50000), 2)
    return_amount = round(base_amount * random.uniform(0.99, 1.0), 2)
    base_date = datetime.now(UTC) - timedelta(days=start_days_ago)
    counterparty = random.choice(COUNTERPARTIES)
    return [
        {
            "account_id": account_id,
            "customer_id": customer_id,
            "amount": f"{base_amount:.2f}",
            "counterparty": counterparty,
            "location": random.choice(LOCATIONS),
            "date": base_date.strftime("%Y-%m-%d"),
            "source_txn_id": _gen_txn_id(),
            "ground_truth": "round_trip",
        },
        {
            "account_id": account_id,
            "customer_id": customer_id,
            "amount": f"{return_amount:.2f}",
            "counterparty": counterparty,
            "location": random.choice(LOCATIONS),
            "date": (base_date + timedelta(hours=random.randint(24, 72))).strftime("%Y-%m-%d"),
            "source_txn_id": _gen_txn_id(),
            "ground_truth": "round_trip",
        },
    ]


def generate_watchlist_row(account_id, customer_id, start_days_ago):
    """Single transaction with a watchlisted counterparty."""
    amount = round(random.uniform(10000, 100000), 2)
    base_date = datetime.now(UTC) - timedelta(days=start_days_ago)
    return {
        "account_id": account_id,
        "customer_id": customer_id,
        "amount": f"{amount:.2f}",
        "counterparty": random.choice(WATCHLIST_COUNTERPARTIES),
        "location": random.choice(LOCATIONS),
        "date": base_date.strftime("%Y-%m-%d"),
        "source_txn_id": _gen_txn_id(),
        "ground_truth": "watchlist",
    }


async def generate(count: int, output: str, manifest_output: str, seed_rules: bool):
    async with async_session_factory() as session:
        result = await session.execute(text("SELECT account_id, customer_id FROM account ORDER BY account_id"))
        accounts = [(row[0], row[1]) for row in result.fetchall()]

    if not accounts:
        print("ERROR: No accounts found. Run 'python -m scripts.seed_db' first.")
        return

    all_rows: list[dict] = []
    manifest: dict[str, str] = {}

    # ── Clean transactions (~98% of total) ──────────────────────
    clean_count = count if count < 25 else int(count * 0.98)
    for i in range(clean_count):
        acct_id, cust_id = random.choice(accounts)
        row = _clean_row(acct_id, cust_id, _gen_txn_id(), days_ago=random.randint(0, 730))
        row["ground_truth"] = ""
        all_rows.append(row)

    # ── Fraud patterns (~2% of total) ───────────────────────────
    # Scale pattern instances so total output ≈ count.
    # Baseline: at count=10000, instances are 6,5,5,5,8 producing ~84 fraud rows.
    pattern_base = [6, 5, 5, 5, 8]
    scale = count / 10000
    pattern_instances = [max(0, round(b * scale)) for b in pattern_base]

    # For medium datasets (count 25-999), ensure at least 1 fraud row
    if count >= 25 and sum(pattern_instances) == 0:
        pattern_instances[-1] = 1  # watchlist (1 row per instance)

    pattern_generators = []
    for name, gen, inst in [
        ("structuring", generate_structuring_set, pattern_instances[0]),
        ("velocity", generate_velocity_set, pattern_instances[1]),
        ("impossible_travel", generate_impossible_travel_pair, pattern_instances[2]),
        ("round_trip", generate_round_trip_pair, pattern_instances[3]),
        ("watchlist", generate_watchlist_row, pattern_instances[4]),
    ]:
        if inst > 0:
            pattern_generators.append((name, gen, inst))

    for pattern_name, generator, instances in pattern_generators:
        for _ in range(instances):
            acct_id, cust_id = random.choice(accounts)
            days_ago = random.randint(0, 730)
            rows = generator(acct_id, cust_id, days_ago)
            if isinstance(rows, list):
                for row in rows:
                    all_rows.append(row)
                    manifest[row["source_txn_id"]] = row["ground_truth"]
            else:
                all_rows.append(rows)
                manifest[rows["source_txn_id"]] = rows["ground_truth"]

    # ── Shuffle all rows ────────────────────────────────────────
    random.shuffle(all_rows)

    # ── Write CSV (append if exists, like stage generators) ─────
    fieldnames = ["account_id", "customer_id", "amount", "counterparty", "location", "date", "source_txn_id"]
    import csv
    output_path = Path(output)
    write_header = not output_path.exists()
    with open(output, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for row in all_rows:
            out_row = {k: row[k] for k in fieldnames}
            writer.writerow(out_row)

    # ── Write manifest ──────────────────────────────────────────
    with open(manifest_output, "w") as f:
        json.dump(manifest, f, indent=2)

    anomalous = sum(1 for r in all_rows if r.get("ground_truth"))
    print(f"Generated {len(all_rows)} transactions -> {output}")
    print(f"  Clean:       {len(all_rows) - anomalous}")
    print(f"  Anomalous:   {anomalous}")
    print(f"  Manifest:    {manifest_output}")

    # ── Seed rules if requested ─────────────────────────────────
    if seed_rules:
        await _seed_rules()

    pattern_counts: dict[str, int] = {}
    for v in manifest.values():
        pattern_counts[v] = pattern_counts.get(v, 0) + 1
    for p, n in sorted(pattern_counts.items()):
        print(f"    {p}: {n}")


async def _seed_rules():
    import json as _json
    from src.aml_workflow.models.rule import Rule
    from datetime import datetime, UTC

    now = datetime.now(UTC).isoformat()
    rules_data = [
        {
            "name": "Structuring Threshold",
            "description": "Flags amounts between $9,500-$9,999, potential structuring",
            "rules_json": _json.dumps([
                {"field": "amount", "operator": ">=", "value": 9500},
                {"field": "amount", "operator": "<=", "value": 9999},
            ]),
        },
        {
            "name": "High Value Transfer",
            "description": "Flags transactions over $10,000",
            "rules_json": _json.dumps([
                {"field": "amount", "operator": ">", "value": 10000},
            ]),
        },
        {
            "name": "Watchlist Counterparty",
            "description": "Flags known high-risk counterparties",
            "rules_json": _json.dumps([
                {"field": "counterparty", "operator": "in", "value": WATCHLIST_COUNTERPARTIES},
            ]),
        },
        {
            "name": "Large Round Amount",
            "description": "Flags suspicious round-number transactions over $5,000",
            "rules_json": _json.dumps([
                {"field": "amount", "operator": ">=", "value": 5000},
                {"field": "amount", "operator": "<=", "value": 5000},
            ]),
        },
    ]

    async with async_session_factory() as session:
        existing = await session.execute(text("SELECT COUNT(*) FROM rule"))
        if existing.scalar() > 0:
            print("  Rules already seeded — skipping.")
            return

        for rd in rules_data:
            rule = Rule(
                id=str(_uuid.uuid4()),
                name=rd["name"],
                description=rd["description"],
                type="deterministic",
                status="active",
                rules_json=rd["rules_json"],
                created_at=now,
                updated_at=now,
            )
            session.add(rule)
        await session.commit()
        print(f"  Seeded {len(rules_data)} rules.")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic fraud pattern dataset")
    parser.add_argument("--count", type=int, default=10000, help="Total transactions (default: 10000)")
    parser.add_argument("--output", type=str, default="data/fraud_dataset.csv", help="Output CSV path")
    parser.add_argument("--manifest", type=str, default=None, help="Output manifest JSON path (default: <output>.manifest.json)")
    parser.add_argument("--seed-rules", action="store_true", help="Seed eval rules into the database")
    args = parser.parse_args()

    manifest_path = args.manifest or (Path(args.output).with_suffix(".manifest.json").as_posix())
    asyncio.run(generate(args.count, args.output, manifest_path, args.seed_rules))


if __name__ == "__main__":
    main()
