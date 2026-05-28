import argparse
import json
from datetime import datetime, UTC

from faker import Faker

from sqlalchemy.exc import SQLAlchemyError

from src.core.models.rule import Rule
from src.core.models.customer import Customer
from src.core.models.account import Account
from src.bff.database import Base, async_session_factory

fake = Faker()

# Real US city/state/zip combos — guarantees valid pairs
_REAL_LOCATIONS = [
    ("New York", "NY", "10001"), ("Los Angeles", "CA", "90001"), ("Chicago", "IL", "60601"),
    ("Houston", "TX", "77001"), ("Phoenix", "AZ", "85001"), ("Philadelphia", "PA", "19101"),
    ("San Antonio", "TX", "78201"), ("San Diego", "CA", "92101"), ("Dallas", "TX", "75201"),
    ("San Jose", "CA", "95101"), ("Austin", "TX", "73301"), ("Jacksonville", "FL", "32099"),
    ("Fort Worth", "TX", "76101"), ("Columbus", "OH", "43085"), ("Charlotte", "NC", "28201"),
    ("Indianapolis", "IN", "46201"), ("San Francisco", "CA", "94101"), ("Seattle", "WA", "98101"),
    ("Denver", "CO", "80201"), ("Nashville", "TN", "37201"), ("Oklahoma City", "OK", "73101"),
    ("El Paso", "TX", "79901"), ("Washington", "DC", "20001"), ("Boston", "MA", "02101"),
    ("Memphis", "TN", "37501"), ("Portland", "OR", "97201"), ("Las Vegas", "NV", "89101"),
    ("Louisville", "KY", "40201"), ("Baltimore", "MD", "21201"), ("Milwaukee", "WI", "53201"),
    ("Albuquerque", "NM", "87101"), ("Tucson", "AZ", "85701"), ("Fresno", "CA", "93650"),
    ("Miami", "FL", "33101"), ("Sacramento", "CA", "94203"), ("Kansas City", "MO", "64101"),
    ("Atlanta", "GA", "30301"), ("Omaha", "NE", "68101"), ("Colorado Springs", "CO", "80901"),
    ("Raleigh", "NC", "27601"), ("Long Beach", "CA", "90801"), ("Virginia Beach", "VA", "23450"),
    ("Miami Beach", "FL", "33139"), ("Oakland", "CA", "94601"), ("Minneapolis", "MN", "55401"),
    ("Tampa", "FL", "33601"), ("Tulsa", "OK", "74101"), ("Arlington", "VA", "22201"),
    ("New Orleans", "LA", "70112"), ("Cleveland", "OH", "44101"),
]


def generate_customer(customer_id: str) -> Customer:
    now = datetime.now(UTC).isoformat()
    city, state, zip_code = fake.random_element(_REAL_LOCATIONS)
    return Customer(
        customer_id=customer_id,
        first_name=fake.first_name(),
        last_name=fake.last_name(),
        address_line=fake.street_address(),
        city=city,
        state=state,
        zip=zip_code,
        created_at=now,
        updated_at=now,
    )


def generate_account(account_id: str, customer_id: str) -> Account:
    now = datetime.now(UTC).isoformat()
    acct_type = fake.random_element(["checking", "savings", "credit"])
    return Account(
        account_id=account_id,
        customer_id=customer_id,
        name=fake.random_element(["Everyday Checking", "Premium Savings", "Basic Checking", "Money Market", "Credit Line"]),
        bank=fake.random_element(["Bank of America", "Chase", "Wells Fargo", "Citi", "US Bank", "PNC"]),
        date_opened=fake.date_between(start_date="-5y", end_date="today").isoformat(),
        type=acct_type,
        created_at=now,
        updated_at=now,
    )


async def seed(num_customers: int, dry_run: bool = False, force: bool = False):
    from sqlalchemy import select, func, text

    async with async_session_factory() as session:
        # Verify database is initialized
        try:
            await session.execute(text("SELECT 1 FROM customer LIMIT 1"))
        except SQLAlchemyError:
            print("ERROR: Database not initialized. Run 'python -m scripts.init_db' first.")
            return

        # Check if already seeded
        result = await session.execute(select(func.count(Customer.customer_id)))
        existing = result.scalar()
        if existing and existing > 0 and not dry_run and not force:
            print(f"Database already has {existing} customers. Use --force to re-seed.")
            return
        elif existing and existing > 0 and force:
            from sqlalchemy import text
            await session.execute(text("DELETE FROM account"))
            await session.execute(text("DELETE FROM customer"))
            await session.execute(text("DELETE FROM rule"))
            await session.commit()
            print("Cleared existing data (force re-seed).")

        customers: list[Customer] = []
        accounts: list[Account] = []
        account_counter = 1

        for i in range(1, num_customers + 1):
            cust_id = f"CUST{i:03d}"
            cust = generate_customer(cust_id)
            customers.append(cust)

            num_accounts = fake.random_int(min=1, max=2)
            for _ in range(num_accounts):
                acc_id = f"ACC{account_counter:03d}"
                accounts.append(generate_account(acc_id, cust_id))
                account_counter += 1

        if dry_run:
            print(f"Dry run — would create:")
            print(f"  Customers: {len(customers)}")
            print(f"  Accounts:  {len(accounts)}")
            print(f"  Accounts per customer: ~{len(accounts) / len(customers):.2f}")
            print(f"  Rules:     7 (High Value Check, Negative Amount, Offshore Location, High Risk Jurisdiction, Offshore Counterparty, Threshold Proximity, Round Amount)")
            return

        session.add_all(customers)
        session.add_all(accounts)

        now = datetime.now(UTC).isoformat()
        rules = [
            Rule(
                name="High Value Check",
                description="Flags transactions over $10,000",
                type="deterministic",
                status="active",
                rules_json=json.dumps([{"field": "amount", "operator": ">", "value": 10000}]),
                created_at=now,
                updated_at=now,
            ),
            Rule(
                name="Negative Amount",
                description="Flags negative transaction amounts",
                type="deterministic",
                status="active",
                rules_json=json.dumps([{"field": "amount", "operator": "<", "value": 0}]),
                created_at=now,
                updated_at=now,
            ),
            Rule(
                name="Offshore Location",
                description="Flags transactions from offshore locations",
                type="deterministic",
                status="active",
                rules_json=json.dumps([{"field": "country", "operator": "==", "value": "Cayman Islands"}]),
                created_at=now,
                updated_at=now,
            ),
            Rule(
                name="High Risk Jurisdiction",
                description="Flags transactions to/from high-risk jurisdictions",
                type="deterministic",
                status="active",
                rules_json=json.dumps([{"field": "country", "operator": "in", "value": ["Iran", "North Korea", "Syria", "Crimea"]}]),
                created_at=now,
                updated_at=now,
            ),
            Rule(
                name="Offshore Counterparty",
                description="Flags transactions with offshore-related counterparties",
                type="deterministic",
                status="active",
                rules_json=json.dumps([{"field": "counterparty", "operator": "contains", "value": "Offshore"}]),
                created_at=now,
                updated_at=now,
            ),
            Rule(
                name="Threshold Proximity",
                description="Flags transaction amounts near reporting threshold",
                type="deterministic",
                status="active",
                rules_json=json.dumps([{"field": "amount", "operator": ">", "value": 8000}]),
                created_at=now,
                updated_at=now,
            ),
            Rule(
                name="Round Amount",
                description="Flags round-dollar amounts often used in structuring",
                type="deterministic",
                status="active",
                rules_json=json.dumps([{"field": "amount", "operator": "in", "value": [1000, 5000, 10000, 20000, 50000]}]),
                created_at=now,
                updated_at=now,
            ),
        ]
        session.add_all(rules)
        await session.commit()

        print(f"Seeding complete:")
        print(f"  Customers created: {len(customers)}")
        print(f"  Accounts created:  {len(accounts)}")
        print(f"  Rules created:     {len(rules)}")


async def run():
    parser = argparse.ArgumentParser(description="Seed database with customers and accounts")
    parser.add_argument("--customers", type=int, default=50, help="Number of customers to create (default: 50)")
    parser.add_argument("--dry-run", action="store_true", help="Preview data without writing")
    parser.add_argument("--force", action="store_true", help="Re-seed even if data exists")
    args = parser.parse_args()

    await seed(args.customers, dry_run=args.dry_run, force=args.force)


def main():
    import asyncio
    asyncio.run(run())


if __name__ == "__main__":
    main()
