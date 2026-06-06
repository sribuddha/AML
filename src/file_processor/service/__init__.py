import contextlib
import json
import math
import uuid as _uuid
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.account import Account
from src.core.models.customer import Customer
from src.bff.config import get_chunk_size, get_upload_dir
from src.file_processor.models import RejectedRecord
from src.core.models.transaction import Transaction
from src.core.models.uploaded_files import UploadedFiles
from src.aml_workflow.services import _set_upload_status, record_transaction_status
from src.core.utils import now as _now

from src.file_processor.service._helpers import (
    REQUIRED_FIELDS,
    HEADER_ALIASES,
    _LOCATION_MAP,
    _expand_location_in_rows,
    _trim_cell,
    _safe_float,
    _clean_nan,
    _is_numeric,
    _write_dbfail,
    _try_insert_rows,
)


async def process_upload(
    df: pd.DataFrame,
    filename: str,
    upload_id: str,
    db: AsyncSession,
    content: bytes | None = None,
):
    now = _now()
    total_rows = len(df)
    chunk_size = get_chunk_size()

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

    await _set_upload_status(db, upload_id, "uploaded")

    await db.flush()

    txn_objs: list[Transaction] = []
    if accepted:
        if accepted_count <= chunk_size:
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
            for chunk_num, chunk_idx in enumerate(range(0, accepted_count, chunk_size)):
                chunk = accepted[chunk_idx:chunk_idx + chunk_size]
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

    now = _now()
    total_accepted = 0
    total_failed = 0

    db_fail_rows: list[dict] = []

    for dbfail_path in sorted(staging_dir.glob("*.dbfail")):
        with open(dbfail_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    db_fail_rows.append(json.loads(line))

    existing_txns = await db.execute(
        select(Transaction.source_txn_id)
    )
    existing_src_ids = {row[0] for row in existing_txns.fetchall()}

    for chunk_id, val_path in enumerate(val_files):
        df = pd.read_csv(val_path, dtype=str)
        rows = df.to_dict(orient="records")

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

    await _set_upload_status(db, upload_id, "complete")
    upload = await db.get(UploadedFiles, upload_id)
    upload.accepted_count = (upload.accepted_count or 0) + total_accepted
    upload.failed_count = (upload.failed_count or 0) + total_failed
    await db.commit()

    return {
        "upload_id": upload_id,
        "filename": upload.filename,
        "status": "completed",
        "accepted_count": total_accepted,
        "failed_count": total_failed,
    }
