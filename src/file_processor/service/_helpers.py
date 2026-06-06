import json
import math
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.transaction import Transaction


REQUIRED_FIELDS = [
    "account_id", "customer_id", "amount",
    "counterparty", "location", "date",
]

HEADER_ALIASES = {
    "account_id": ["account_id", "account id", "acct", "account"],
    "customer_id": ["customer_id", "customer id", "custid", "customer"],
    "amount": ["amount", "amt", "value"],
    "counterparty": ["counterparty", "counter party", "cp", "payee"],
    "location": ["location", "loc", "branch"],
    "date": ["date", "txn_date", "transaction_date", "trans_date"],
}

_LOCATION_MAP: dict[str, tuple[str, str, str]] = {
    "New York": ("New York", "NY", "US"),
    "London": ("London", "", "GB"),
    "Chicago": ("Chicago", "IL", "US"),
    "Boston": ("Boston", "MA", "US"),
    "Dallas": ("Dallas", "TX", "US"),
    "Miami": ("Miami", "FL", "US"),
    "Seattle": ("Seattle", "WA", "US"),
    "Denver": ("Denver", "CO", "US"),
    "San Francisco": ("San Francisco", "CA", "US"),
    "Los Angeles": ("Los Angeles", "CA", "US"),
    "Austin": ("Austin", "TX", "US"),
    "Atlanta": ("Atlanta", "GA", "US"),
    "Portland": ("Portland", "OR", "US"),
    "Phoenix": ("Phoenix", "AZ", "US"),
    "Toronto": ("Toronto", "ON", "CA"),
    "Iran": ("", "", "Iran"),
    "North Korea": ("", "", "North Korea"),
    "Syria": ("", "", "Syria"),
    "Crimea": ("", "", "Crimea"),
    "Cayman": ("George Town", "", "Cayman Islands"),
    "Tokyo": ("Tokyo", "", "Japan"),
    "Dubai": ("Dubai", "", "UAE"),
    "Lagos": ("Lagos", "", "Nigeria"),
    "Singapore": ("Singapore", "", "Singapore"),
    "NY": ("New York", "NY", "US"),
    "CA": ("", "CA", "US"),
    "MA": ("", "MA", "US"),
    "TX": ("", "TX", "US"),
    "LA": ("Los Angeles", "CA", "US"),
    "XX": ("", "", ""),
}


def _expand_location_in_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split location into city/state/country. Returns (valid, rejected)."""
    valid: list[dict] = []
    rejected: list[dict] = []
    for row in rows:
        loc_raw = row.get("location", "")
        entry = _LOCATION_MAP.get(loc_raw)
        if entry is None:
            rejected.append(row)
            continue
        city_name, state_name, country_name = entry
        row["city"] = city_name
        row["state"] = state_name
        row["country"] = country_name
        del row["location"]
        valid.append(row)
    return valid, rejected


def _trim_cell(value: str) -> str:
    if not isinstance(value, str):
        return value
    return value.strip().strip('"').strip()


def _safe_float(value: float) -> float:
    if isinstance(value, float) and math.isnan(value):
        return 0.0
    return float(value)


def _clean_nan(obj):
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nan(v) for v in obj]
    return obj


def _is_numeric(value) -> bool:
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def _write_dbfail(staging_dir: Path, chunk_id: str, row: dict):
    dbfail_path = staging_dir / f"{chunk_id}.dbfail"
    with open(dbfail_path, "a") as f:
        f.write(json.dumps(row) + "\n")


async def _try_insert_rows(
    session: AsyncSession,
    rows: list[dict],
    upload_id: str,
    now: str,
    staging_dir: Path,
    chunk_id: str,
) -> tuple[int, int]:
    if not rows:
        return 0, 0

    for r in rows:
        r["upload_id"] = upload_id
        r["created_at"] = now
        r["updated_at"] = now

    inserted = 0
    failed = 0

    objs = [Transaction(**r) for r in rows]
    try:
        session.add_all(objs)
        await session.flush()
        inserted = len(rows)
    except SQLAlchemyError:
        for obj in objs:
            session.expunge(obj)
        for row in rows:
            try:
                session.add(Transaction(**row))
                await session.flush()
                inserted += 1
            except SQLAlchemyError:
                _write_dbfail(staging_dir, chunk_id, row)
                failed += 1

    return inserted, failed
