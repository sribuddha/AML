import os
import uuid
from datetime import datetime, UTC

import pandas as pd
import pytest
from sqlalchemy import select, func

from src.bff.config import UPLOAD_DIR
from src.file_processor.models import Transaction, UploadedFiles
import src.file_processor.service as service


@pytest.mark.asyncio
async def test_upload_fewer_rows_than_chunk_size(seeded_session):
    upload_id = str(uuid.uuid4())
    rows = []
    for i in range(50):
        rows.append({
            "account_id": "ACC001",
            "customer_id": "CUST001",
            "amount": 100.0 + i,
            "counterparty": f"Counterparty_{i}",
            "location": "New York",
            "date": "2024-01-15",
            "source_txn_id": f"T{i:04d}",
        })
    df = pd.DataFrame(rows)
    result = await service.process_upload(df, "small.csv", upload_id, seeded_session)
    assert result["total_rows"] == 50
    assert result["accepted_count"] == 50
    assert result["failed_count"] == 0

    count = (await seeded_session.execute(
        select(func.count()).select_from(Transaction).where(Transaction.upload_id == upload_id)
    )).scalar()
    assert count == 50


@pytest.mark.asyncio
async def test_upload_more_rows_than_chunk_size(seeded_session, monkeypatch):
    monkeypatch.setenv("AML_CHUNK_SIZE", "500")
    monkeypatch.setattr(service, "CHUNK_SIZE", 500)
    upload_id = str(uuid.uuid4())
    rows = []
    for i in range(501):
        rows.append({
            "account_id": "ACC001",
            "customer_id": "CUST001",
            "amount": 200.0 + i,
            "counterparty": f"Partner_{i}",
            "location": "New York",
            "date": "2024-02-10",
            "source_txn_id": f"S{i:04d}",
        })
    df = pd.DataFrame(rows)
    result = await service.process_upload(df, "large.csv", upload_id, seeded_session)
    assert result["total_rows"] == 501
    assert result["accepted_count"] == 501
    assert result["failed_count"] == 0

    count = (await seeded_session.execute(
        select(func.count()).select_from(Transaction).where(Transaction.upload_id == upload_id)
    )).scalar()
    assert count == 501


@pytest.mark.asyncio
async def test_upload_unknown_location_rejected(seeded_session):
    now = datetime.now(UTC).isoformat()
    upload_id = str(uuid.uuid4())

    upload = UploadedFiles(
        id=upload_id, filename="unknown_loc.csv", status="failed",
        total_rows=3, accepted_count=0, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    await seeded_session.commit()

    staging_dir = UPLOAD_DIR / "staging" / upload_id
    staging_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100.0,
         "counterparty": "Known Co", "location": "New York", "date": "2024-01-15",
         "source_txn_id": "LOC001"},
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 200.0,
         "counterparty": "Unknown Co", "location": "Unknown", "date": "2024-01-16",
         "source_txn_id": "LOC002"},
        {"account_id": "ACC002", "customer_id": "CUST001", "amount": 300.0,
         "counterparty": "Other Co", "location": "Chicago", "date": "2024-01-17",
         "source_txn_id": "LOC003"},
    ]
    val_df = pd.DataFrame(rows)
    val_df.to_csv(staging_dir / "0.val", index=False)

    result = await service.retry_upload(upload_id, seeded_session)
    assert result["accepted_count"] == 2
    assert result["failed_count"] == 1

    count = (await seeded_session.execute(
        select(func.count()).select_from(Transaction).where(Transaction.upload_id == upload_id)
    )).scalar()
    assert count == 2


@pytest.mark.asyncio
async def test_upload_empty_csv(seeded_session):
    upload_id = str(uuid.uuid4())
    df = pd.DataFrame(columns=[
        "account_id", "customer_id", "amount", "counterparty",
        "location", "date", "source_txn_id",
    ])
    result = await service.process_upload(df, "empty.csv", upload_id, seeded_session)
    assert result["total_rows"] == 0
    assert result["accepted_count"] == 0
    assert result["failed_count"] == 0

    count = (await seeded_session.execute(
        select(func.count()).select_from(Transaction).where(Transaction.upload_id == upload_id)
    )).scalar()
    assert count == 0
