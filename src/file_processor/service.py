import contextlib
import json
import math
import os
import uuid as _uuid
from datetime import datetime, UTC
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.account import Account
from src.core.models.customer import Customer
from src.bff.config import get_upload_dir
from src.file_processor.models import RejectedRecord
from src.core.models.transaction import Transaction
from src.core.models.uploaded_files import UploadedFiles
from src.aml_workflow.services import record_transaction_status

CHUNK_SIZE = int(os.environ.get("AML_CHUNK_SIZE", "10000"))

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

# Maps CSV location values to (city, state, country) tuples.
# Every known location must be here — unknown values are rejected at upload.
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

    try:
        objs = [Transaction(**r) for r in rows]
        session.add_all(objs)
        await session.flush()
        inserted = len(rows)
    except Exception:
        for row in rows:
            try:
                session.add(Transaction(**row))
                await session.flush()
                inserted += 1
            except Exception:
                _write_dbfail(staging_dir, chunk_id, row)
                failed += 1

    return inserted, failed


def _clean_nan(obj):
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nan(v) for v in obj]
    return obj


async def process_upload(
    df: pd.DataFrame,
    filename: str,
    upload_id: str,
    db: AsyncSession,
    content: bytes | None = None,
):
    now = datetime.now(UTC).isoformat()
    total_rows = len(df)

    staging_dir = get_upload_dir() / "staging" / upload_id
    staging_dir.mkdir(parents=True, exist_ok=True)

    if content:
        (staging_dir / f"{filename}.orig").write_bytes(content)

    rejected: list[dict] = []
    accepted: list[dict] = []
    rejected_preview: list[dict] = []
    fail_lines: list[str] = []

    pending: list[tuple[int, dict]] = []
    pending_account_ids: set[str] = set()
    pending_customer_ids: set[str] = set()

    for idx, row in df.iterrows():
        reasons: list[str] = []

        for field in REQUIRED_FIELDS:
            val = row.get(field)
            if isinstance(val, float) and math.isnan(val):
                reasons.append(f"{field} is required")

        account_id_raw = row.get("account_id")
        if account_id_raw is None or (isinstance(account_id_raw, str) and not account_id_raw.strip()):
            reasons.append("Missing account_id")

        customer_id_raw = row.get("customer_id")
        if customer_id_raw is None or (isinstance(customer_id_raw, str) and not customer_id_raw.strip()):
            reasons.append("Missing customer_id")

        amount_raw = row.get("amount")
        if amount_raw is None or (isinstance(amount_raw, str) and not amount_raw.strip()):
            reasons.append("Missing amount")
        elif not _is_numeric(amount_raw):
            reasons.append("Amount is not numeric")

        date_raw = row.get("date")
        if date_raw is not None and isinstance(date_raw, str) and date_raw.strip():
            try:
                from datetime import datetime as dt
                dt.strptime(date_raw.strip(), "%Y-%m-%d")
            except (ValueError, TypeError):
                reasons.append("not a valid date")

        if reasons:
            fail_entry = {"row_index": idx, "raw_data": dict(row), "reasons": reasons}
            rejected.append(fail_entry)
            fail_lines.append(json.dumps(fail_entry))
            if len(rejected_preview) < 10:
                clean_raw = _clean_nan(dict(row))
                rejected_preview.append({"row": idx, "raw_data": clean_raw, "reasons": reasons})
            continue

        amount_val = _safe_float(float(amount_raw))

        cleaned = {field: _trim_cell(str(row.get(field, ""))) for field in REQUIRED_FIELDS}
        cleaned["amount"] = amount_val

        pending_account_ids.add(cleaned["account_id"])
        pending_customer_ids.add(cleaned["customer_id"])
        pending.append((idx, dict(row), cleaned, amount_val))

    # Batch FK lookups: two queries instead of N*2
    valid_account_ids: set[str] = set()
    if pending_account_ids:
        acct_rows = await db.execute(
            select(Account.account_id).where(Account.account_id.in_(list(pending_account_ids)))
        )
        valid_account_ids = {r[0] for r in acct_rows.fetchall()}

    valid_customer_ids: set[str] = set()
    if pending_customer_ids:
        cust_rows = await db.execute(
            select(Customer.customer_id).where(Customer.customer_id.in_(list(pending_customer_ids)))
        )
        valid_customer_ids = {r[0] for r in cust_rows.fetchall()}

    for idx, orig_row, cleaned, amount_val in pending:
        reasons: list[str] = []
        account_id = cleaned["account_id"]
        customer_id = cleaned["customer_id"]

        if account_id not in valid_account_ids:
            reasons.append("account_id not found")
        if customer_id not in valid_customer_ids:
            reasons.append("customer_id not found")

        location_raw = cleaned.get("location", "")
        loc_entry = _LOCATION_MAP.get(location_raw)
        if loc_entry is None:
            reasons.append(f"Unknown location: {location_raw}")
        else:
            city_name, state_name, country_name = loc_entry

        if reasons:
            fail_entry = {"row_index": idx, "raw_data": orig_row, "reasons": reasons}
            rejected.append(fail_entry)
            fail_lines.append(json.dumps(fail_entry))
            if len(rejected_preview) < 10:
                clean_raw = _clean_nan(orig_row)
                rejected_preview.append({"row": idx, "raw_data": clean_raw, "reasons": reasons})
            continue

        accepted.append({
            "account_id": account_id,
            "customer_id": customer_id,
            "amount": amount_val,
            "counterparty": cleaned.get("counterparty", ""),
            "city": city_name,
            "state": state_name,
            "country": country_name,
            "date": cleaned.get("date", ""),
            "source_txn_id": str(orig_row.get("source_txn_id", f"TXN-{idx:06d}")),
            "created_at": now,
            "updated_at": now,
        })

    accepted_count = len(accepted)
    failed_count = len(rejected)

    upload_obj = UploadedFiles(
        id=upload_id,
        filename=filename,
        status="uploaded",
        total_rows=total_rows,
        accepted_count=accepted_count,
        failed_count=failed_count,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(upload_obj)

    from src.aml_workflow.services import _set_upload_status
    await _set_upload_status(db, upload_id, "uploaded")

    await db.flush()

    txn_objs: list[Transaction] = []
    if accepted:
        if accepted_count <= CHUNK_SIZE:
            val_path = staging_dir / "0.val"
            val_df = pd.DataFrame(accepted)
            val_df.to_csv(val_path, index=False)

            for txn_data in accepted:
                txn_data["upload_id"] = upload_id
                obj = Transaction(**txn_data)
                db.add(obj)
                txn_objs.append(obj)
            await db.flush()

            val_path.rename(staging_dir / "0.val.db")
        else:
            for chunk_num, chunk_idx in enumerate(range(0, accepted_count, CHUNK_SIZE)):
                chunk = accepted[chunk_idx:chunk_idx + CHUNK_SIZE]
                for txn_data in chunk:
                    txn_data["upload_id"] = upload_id
                    obj = Transaction(**txn_data)
                    db.add(obj)
                    txn_objs.append(obj)
                await db.flush()

                chunk_row = UploadedFiles(
                    id=str(_uuid.uuid4()),
                    filename=f"{filename}.{chunk_num}",
                    upload_chunk=chunk_num,
                    status="committed",
                    total_rows=len(chunk),
                    accepted_count=len(chunk),
                    failed_count=0,
                    uploaded_at=now,
                    created_at=now,
                    updated_at=now,
                )
                db.add(chunk_row)
            await db.flush()

        for obj in txn_objs:
            await record_transaction_status(db, obj.id, "loaded")
        await db.flush()

    for rej in rejected:
        rej_data = dict(rej)
        db.add(RejectedRecord(
            upload_id=upload_id,
            row_index=rej_data["row_index"],
            raw_data=json.dumps(rej_data["raw_data"]),
            reasons=json.dumps(rej_data["reasons"]),
            created_at=now,
            updated_at=now,
        ))

    if fail_lines:
        fail_path = staging_dir / "0.fail"
        fail_path.write_text("\n".join(fail_lines))

    await db.commit()
    await db.refresh(upload_obj)

    return {
        "upload_id": upload_id,
        "filename": filename,
        "status": "completed",
        "total_rows": total_rows,
        "accepted_count": accepted_count,
        "failed_count": failed_count,
        "rejected_preview": rejected_preview,
    }


def _is_numeric(value) -> bool:
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


async def retry_upload(upload_id: str, db: AsyncSession):
    upload = await db.get(UploadedFiles, upload_id)
    if upload is None:
        raise ValueError("Upload not found")

    staging_dir = get_upload_dir() / "staging" / upload_id
    if not staging_dir.exists():
        raise ValueError(f"Staging directory not found: {staging_dir}")

    val_files = sorted(staging_dir.glob("*.val"))
    if not val_files:
        raise ValueError("No .val files found")

    now = datetime.now(UTC).isoformat()
    total_accepted = 0
    total_failed = 0

    db_fail_rows: list[dict] = []

    for dbfail_path in sorted(staging_dir.glob("*.dbfail")):
        with open(dbfail_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    db_fail_rows.append(json.loads(line))

    for chunk_id, val_path in enumerate(val_files):
        df = pd.read_csv(val_path, dtype=str)
        rows = df.to_dict(orient="records")

        existing_txns = await db.execute(
            select(Transaction.source_txn_id)
        )
        existing_src_ids = {row[0] for row in existing_txns.fetchall()}

        new_rows = [r for r in rows if r.get("source_txn_id") not in existing_src_ids]

        dbfail_chunk = staging_dir / f"{chunk_id}.dbfail"
        new_dbfail_rows: list[dict] = []
        for row in db_fail_rows:
            if row.get("source_txn_id") not in existing_src_ids:
                new_dbfail_rows.append(row)

        with contextlib.suppress(FileNotFoundError):
            if dbfail_chunk.exists():
                dbfail_chunk.unlink()

        all_rows = new_rows + new_dbfail_rows

        if all_rows:
            valid_rows, rejected_rows = _expand_location_in_rows(all_rows)
            total_failed += len(rejected_rows)
            if valid_rows:
                inserted, failed = await _try_insert_rows(
                    db, valid_rows, upload_id, now, staging_dir, str(chunk_id)
                )
                total_accepted += inserted
                total_failed += failed
        else:
            total_failed += len(db_fail_rows) - len(new_dbfail_rows)

    upload.status = "completed"
    upload.accepted_count = (upload.accepted_count or 0) + total_accepted
    upload.failed_count = (upload.failed_count or 0) + total_failed
    upload.updated_at = now
    await db.commit()

    return {
        "upload_id": upload_id,
        "filename": upload.filename,
        "status": "completed",
        "accepted_count": total_accepted,
        "failed_count": total_failed,
    }
