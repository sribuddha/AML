import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

import uuid

from src.bff.config import get_upload_dir
from src.file_processor.service import process_upload


@pytest.mark.asyncio
async def test_all_valid_rows_accepted(seeded_session):
    df = pd.DataFrame([
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 1500.00,
         "counterparty": "Acme Corp", "location": "New York", "date": "2026-05-01",
         "source_txn_id": "TXN001"},
        {"account_id": "ACC003", "customer_id": "CUST002", "amount": 250.00,
         "counterparty": "Global Ltd", "location": "London", "date": "2026-05-02",
         "source_txn_id": "TXN002"},
    ])
    result = await process_upload(df, "valid.csv", str(uuid.uuid4()), seeded_session)
    assert result["total_rows"] == 2
    assert result["accepted_count"] == 2
    assert result["failed_count"] == 0
    assert len(result["rejected_preview"]) == 0
    assert result["filename"] == "valid.csv"


@pytest.mark.asyncio
async def test_empty_csv(seeded_session):
    df = pd.DataFrame(columns=["account_id", "customer_id", "amount", "counterparty", "location", "date", "source_txn_id"])
    result = await process_upload(df, "empty.csv", str(uuid.uuid4()), seeded_session)
    assert result["total_rows"] == 0
    assert result["accepted_count"] == 0
    assert result["failed_count"] == 0


@pytest.mark.asyncio
async def test_missing_required_fields(seeded_session):
    df = pd.DataFrame([
        {"account_id": "", "customer_id": "CUST001", "amount": 100.00,
         "counterparty": "Co", "location": "NY", "date": "2026-05-01",
         "source_txn_id": "TXN005"},
        {"account_id": "ACC001", "customer_id": None, "amount": 200.00,
         "counterparty": "Co", "location": "NY", "date": "2026-05-01",
         "source_txn_id": "TXN006"},
    ])
    result = await process_upload(df, "missing.csv", str(uuid.uuid4()), seeded_session)
    assert result["total_rows"] == 2
    assert result["accepted_count"] == 0
    assert result["failed_count"] == 2
    assert any("account_id" in r["reasons"][0] for r in result["rejected_preview"])
    assert any("customer_id" in r["reasons"][0] for r in result["rejected_preview"])


@pytest.mark.asyncio
async def test_non_numeric_amount(seeded_session):
    df = pd.DataFrame([
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": "abc",
         "counterparty": "Co", "location": "NY", "date": "2026-05-01",
         "source_txn_id": "TXN007"},
    ])
    result = await process_upload(df, "bad_amount.csv", str(uuid.uuid4()), seeded_session)
    assert result["accepted_count"] == 0
    assert result["failed_count"] == 1
    assert any("not numeric" in r["reasons"][0] for r in result["rejected_preview"])


@pytest.mark.asyncio
async def test_invalid_date(seeded_session):
    df = pd.DataFrame([
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100.00,
         "counterparty": "Co", "location": "NY", "date": "not-a-date",
         "source_txn_id": "TXN008"},
    ])
    result = await process_upload(df, "bad_date.csv", str(uuid.uuid4()), seeded_session)
    assert result["accepted_count"] == 0
    assert result["failed_count"] == 1
    assert any("not a valid date" in r["reasons"][0] for r in result["rejected_preview"])


@pytest.mark.asyncio
async def test_account_id_not_found(seeded_session):
    df = pd.DataFrame([
        {"account_id": "DOES_NOT_EXIST", "customer_id": "CUST001", "amount": 100.00,
         "counterparty": "Co", "location": "NY", "date": "2026-05-01",
         "source_txn_id": "TXN009"},
    ])
    result = await process_upload(df, "bad_fk.csv", str(uuid.uuid4()), seeded_session)
    assert result["accepted_count"] == 0
    assert result["failed_count"] == 1
    assert any("not found" in r["reasons"][0] for r in result["rejected_preview"])


@pytest.mark.asyncio
async def test_customer_id_not_found(seeded_session):
    df = pd.DataFrame([
        {"account_id": "ACC001", "customer_id": "DOES_NOT_EXIST", "amount": 100.00,
         "counterparty": "Co", "location": "NY", "date": "2026-05-01",
         "source_txn_id": "TXN010"},
    ])
    result = await process_upload(df, "bad_cust.csv", str(uuid.uuid4()), seeded_session)
    assert result["accepted_count"] == 0
    assert result["failed_count"] == 1
    assert any("not found" in r["reasons"][0] for r in result["rejected_preview"])


@pytest.mark.asyncio
async def test_mixed_valid_and_invalid(seeded_session):
    df = pd.DataFrame([
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100.00,
         "counterparty": "Good", "location": "NY", "date": "2026-05-01",
         "source_txn_id": "TXN011"},
        {"account_id": "BAD_ACC", "customer_id": "CUST001", "amount": 200.00,
         "counterparty": "Bad", "location": "LA", "date": "2026-05-02",
         "source_txn_id": "TXN012"},
        {"account_id": "ACC002", "customer_id": "CUST001", "amount": 300.00,
         "counterparty": "Good", "location": "Chicago", "date": "2026-05-03",
         "source_txn_id": "TXN013"},
    ])
    result = await process_upload(df, "mixed.csv", str(uuid.uuid4()), seeded_session)
    assert result["total_rows"] == 3
    assert result["accepted_count"] == 2
    assert result["failed_count"] == 1
    assert len(result["rejected_preview"]) == 1


@pytest.mark.asyncio
async def test_rejected_preview_limited_to_10(seeded_session):
    rows = [
        {"account_id": f"BAD{i:03d}", "customer_id": "CUST001", "amount": 100.00,
         "counterparty": "Co", "location": "NY", "date": "2026-05-01",
         "source_txn_id": f"TXN{i:04d}"}
        for i in range(20)
    ]
    df = pd.DataFrame(rows)
    result = await process_upload(df, "many_bad.csv", str(uuid.uuid4()), seeded_session)
    assert result["total_rows"] == 20
    assert result["accepted_count"] == 0
    assert result["failed_count"] == 20
    assert len(result["rejected_preview"]) == 10


@pytest.mark.asyncio
async def test_upload_creates_db_records(seeded_session):
    df = pd.DataFrame([
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 500.00,
         "counterparty": "Acme", "location": "Boston", "date": "2026-06-01",
         "source_txn_id": "TXN020"},
        {"account_id": "ACC003", "customer_id": "CUST002", "amount": 999.99,
         "counterparty": "Beta", "location": "Dallas", "date": "2026-06-02",
         "source_txn_id": "TXN021"},
    ])
    result = await process_upload(df, "db_test.csv", str(uuid.uuid4()), seeded_session)
    upload_id = result["upload_id"]

    from src.file_processor.models import RejectedRecord
    from src.core.models.transaction import Transaction
    from src.core.models.uploaded_files import UploadedFiles
    from sqlalchemy import select

    upload = (await seeded_session.execute(
        select(UploadedFiles).where(UploadedFiles.id == upload_id)
    )).scalar_one()
    assert upload.filename == "db_test.csv"
    assert upload.accepted_count == 2
    assert upload.failed_count == 0
    assert upload.status == "uploaded"

    txns = (await seeded_session.execute(
        select(Transaction).where(Transaction.upload_id == upload_id)
    )).scalars().all()
    assert len(txns) == 2
    assert txns[0].amount == 500.00
    assert txns[0].source_txn_id == "TXN020"
    assert txns[1].amount == 999.99
    assert txns[1].source_txn_id == "TXN021"

    rejects = (await seeded_session.execute(
        select(RejectedRecord).where(RejectedRecord.upload_id == upload_id)
    )).scalars().all()
    assert len(rejects) == 0


@pytest.mark.asyncio
async def test_rejected_rows_stored_in_db(seeded_session):
    df = pd.DataFrame([
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100.00,
         "counterparty": "Co", "location": "NY", "date": "2026-05-01",
         "source_txn_id": "TXN022"},
        {"account_id": "FAKE_ACC", "customer_id": "CUST001", "amount": 200.00,
         "counterparty": "Co", "location": "LA", "date": "2026-05-02",
         "source_txn_id": "TXN023"},
    ])
    result = await process_upload(df, "reject_db.csv", str(uuid.uuid4()), seeded_session)

    from src.file_processor.models import RejectedRecord
    from sqlalchemy import select

    rejects = (await seeded_session.execute(
        select(RejectedRecord).where(RejectedRecord.upload_id == result["upload_id"])
    )).scalars().all()
    assert len(rejects) == 1
    reasons = json.loads(rejects[0].reasons)
    assert any("not found" in r for r in reasons)


@pytest.mark.asyncio
async def test_nan_required_field_caught(seeded_session):
    df = pd.DataFrame([
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100.00,
         "counterparty": float("nan"), "location": "NY", "date": "2026-05-01",
         "source_txn_id": "TXN030"},
    ])
    result = await process_upload(df, "nan_test.csv", str(uuid.uuid4()), seeded_session)
    assert result["accepted_count"] == 0
    assert result["failed_count"] == 1
    assert any("counterparty" in r["reasons"][0] for r in result["rejected_preview"])


@pytest.mark.asyncio
async def test_staging_dir_created_with_fail_files(seeded_session):
    df = pd.DataFrame([
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100.00,
         "counterparty": "Co", "location": "NY", "date": "2026-05-01",
         "source_txn_id": "TXN040"},
        {"account_id": "BAD001", "customer_id": "CUST001", "amount": 200.00,
         "counterparty": "Co", "location": "LA", "date": "2026-05-02",
         "source_txn_id": "TXN041"},
    ])
    result = await process_upload(df, "staging_test.csv", str(uuid.uuid4()), seeded_session)
    upload_id = result["upload_id"]
    staging_dir = get_upload_dir() / "staging" / str(upload_id)

    assert staging_dir.exists()
    assert (staging_dir / "0.val.db").exists()
    assert not (staging_dir / "0.val").exists()
    assert (staging_dir / "0.fail").exists()
    fail_content = (staging_dir / "0.fail").read_text()
    assert "BAD001" in fail_content


@pytest.mark.asyncio
async def test_retry_not_found(seeded_session):
    from src.file_processor.service import retry_upload
    import pytest as _pytest

    with _pytest.raises(ValueError, match="Upload not found"):
        await retry_upload("nonexistent", seeded_session)


@pytest.mark.asyncio
async def test_retry_no_staging_dir(seeded_session):
    from src.file_processor.service import retry_upload
    from src.core.models.uploaded_files import UploadedFiles
    from datetime import datetime, UTC
    import uuid
    import pytest as _pytest

    upload_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    upload = UploadedFiles(
        id=upload_id, filename="test.csv", status="failed",
        total_rows=1, accepted_count=1, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    await seeded_session.commit()

    with _pytest.raises(ValueError, match="Staging directory not found"):
        await retry_upload(upload_id, seeded_session)


@pytest.mark.asyncio
async def test_retry_no_val_files(seeded_session):
    from src.file_processor.service import retry_upload
    from src.core.models.uploaded_files import UploadedFiles
    from src.bff.config import get_upload_dir
    from datetime import datetime, UTC
    import uuid
    import pytest as _pytest

    upload_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    upload = UploadedFiles(
        id=upload_id, filename="test.csv", status="failed",
        total_rows=1, accepted_count=1, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    await seeded_session.commit()

    staging_dir = get_upload_dir() / "staging" / upload_id
    staging_dir.mkdir(parents=True, exist_ok=True)

    with _pytest.raises(ValueError, match="No .val files found"):
        await retry_upload(upload_id, seeded_session)


@pytest.mark.asyncio
async def test_retry_success(seeded_session):
    from src.file_processor.service import retry_upload
    from src.core.models.transaction import Transaction
    from src.core.models.uploaded_files import UploadedFiles
    from src.bff.config import get_upload_dir
    from datetime import datetime, UTC
    from sqlalchemy import select
    import uuid
    import pandas as pd

    failed_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    upload = UploadedFiles(
        id=failed_id, filename="retry_unit.csv", status="failed",
        total_rows=2, accepted_count=2, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    await seeded_session.commit()

    staging_dir = get_upload_dir() / "staging" / failed_id
    staging_dir.mkdir(parents=True, exist_ok=True)
    val_df = pd.DataFrame([
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100.00,
         "counterparty": "Co", "location": "NY", "date": "2026-06-01",
         "source_txn_id": "RETRY_UNIT_001"},
        {"account_id": "ACC003", "customer_id": "CUST002", "amount": 200.00,
         "counterparty": "Co", "location": "LA", "date": "2026-06-02",
         "source_txn_id": "RETRY_UNIT_002"},
    ])
    val_df.to_csv(staging_dir / "0.val", index=False)

    result = await retry_upload(failed_id, seeded_session)
    assert result["accepted_count"] == 2
    assert result["failed_count"] == 0
    assert result["filename"] == "retry_unit.csv"

    txns = (await seeded_session.execute(
        select(Transaction).where(Transaction.upload_id == result["upload_id"])
    )).scalars().all()
    assert len(txns) == 2


@pytest.mark.asyncio
async def test_retry_idempotency_skips_duplicates(seeded_session):
    from src.file_processor.service import retry_upload
    from src.core.models.transaction import Transaction
    from src.core.models.uploaded_files import UploadedFiles
    from src.bff.config import get_upload_dir
    from datetime import datetime, UTC
    from sqlalchemy import select
    import uuid
    import pandas as pd

    prev_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    prev_upload = UploadedFiles(
        id=prev_id, filename="dedup_test.csv", status="failed",
        total_rows=1, accepted_count=1, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(prev_upload)
    await seeded_session.flush()

    existing_tx = Transaction(
        upload_id=prev_id,
        account_id="ACC001",
        customer_id="CUST001",
        amount=100.00,
        counterparty="Co",
        city="New York", state="NY", country="US",
        date="2026-06-01",
        source_txn_id="DEDUP001",
        created_at=now,
        updated_at=now,
    )
    seeded_session.add(existing_tx)
    await seeded_session.commit()

    failed_id = str(uuid.uuid4())
    upload = UploadedFiles(
        id=failed_id, filename="dedup_test.csv", status="failed",
        total_rows=2, accepted_count=2, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    await seeded_session.commit()

    staging_dir = get_upload_dir() / "staging" / failed_id
    staging_dir.mkdir(parents=True, exist_ok=True)
    val_df = pd.DataFrame([
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100.00,
         "counterparty": "Co", "location": "NY", "date": "2026-06-01",
         "source_txn_id": "DEDUP001"},
        {"account_id": "ACC003", "customer_id": "CUST002", "amount": 200.00,
         "counterparty": "Co", "location": "LA", "date": "2026-06-02",
         "source_txn_id": "DEDUP002"},
    ])
    val_df.to_csv(staging_dir / "0.val", index=False)

    result = await retry_upload(failed_id, seeded_session)
    assert result["accepted_count"] == 1

    txns = (await seeded_session.execute(
        select(Transaction).where(Transaction.upload_id == result["upload_id"])
    )).scalars().all()
    assert len(txns) == 1
    assert txns[0].source_txn_id == "DEDUP002"


@pytest.mark.asyncio
async def test_try_insert_rows_empty_returns_zero(seeded_session):
    from src.file_processor.service import _try_insert_rows
    from datetime import datetime, UTC

    now = datetime.now(UTC).isoformat()
    staging_dir = get_upload_dir() / "staging" / "_empty_test"
    staging_dir.mkdir(parents=True, exist_ok=True)

    inserted, failed = await _try_insert_rows(seeded_session, [], "_upload_id", now, staging_dir, "0")
    assert inserted == 0
    assert failed == 0
    shutil.rmtree(staging_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_write_dbfail_creates_file(seeded_session):
    from src.file_processor.service import _write_dbfail
    from src.bff.config import get_upload_dir
    import shutil

    staging_dir = get_upload_dir() / "staging" / "_dbfail_write_test"
    staging_dir.mkdir(parents=True, exist_ok=True)

    row = {"account_id": "ACC001", "source_txn_id": "DBFAIL_WRITE"}
    _write_dbfail(staging_dir, "0", row)

    dbfail_path = staging_dir / "0.dbfail"
    assert dbfail_path.exists()
    content = dbfail_path.read_text()
    assert "DBFAIL_WRITE" in content
    shutil.rmtree(staging_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_try_insert_rows_bulk_fail_triggers_individual_fallback(seeded_session):
    from src.file_processor.service import _try_insert_rows
    from src.core.models.uploaded_files import UploadedFiles
    from src.bff.config import get_upload_dir
    from datetime import datetime, UTC
    from sqlalchemy.exc import SQLAlchemyError
    from unittest.mock import patch
    import uuid

    now = datetime.now(UTC).isoformat()
    upload_id = str(uuid.uuid4())
    upload = UploadedFiles(
        id=upload_id, filename="bulk_fail.csv", status="processing",
        total_rows=2, uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    await seeded_session.flush()

    staging_dir = get_upload_dir() / "staging" / upload_id
    staging_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100.00,
         "counterparty": "Co", "city": "New York", "state": "NY", "country": "US", "date": "2026-06-01",
         "source_txn_id": "BULKFAIL001"},
        {"account_id": "ACC003", "customer_id": "CUST002", "amount": 200.00,
         "counterparty": "Co", "city": "Los Angeles", "state": "CA", "country": "US", "date": "2026-06-02",
         "source_txn_id": "BULKFAIL002"},
    ]

    original_flush = seeded_session.flush
    call_count = 0

    async def failing_flush():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise SQLAlchemyError("Bulk flush failed")
        return await original_flush()

    with patch.object(seeded_session, "flush", failing_flush):
        inserted, failed = await _try_insert_rows(
            seeded_session, rows, upload_id, now, staging_dir, "0"
        )

    assert inserted == 2
    assert failed == 0


@pytest.mark.asyncio
async def test_retry_processes_dbfail_files(seeded_session):
    from src.file_processor.service import retry_upload
    from src.core.models.transaction import Transaction
    from src.core.models.uploaded_files import UploadedFiles
    from src.bff.config import get_upload_dir
    from datetime import datetime, UTC
    from sqlalchemy import select
    import uuid
    import json
    import pandas as pd

    failed_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    upload = UploadedFiles(
        id=failed_id, filename="dbfail_retry.csv", status="failed",
        total_rows=2, accepted_count=2, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    await seeded_session.commit()

    staging_dir = get_upload_dir() / "staging" / failed_id
    staging_dir.mkdir(parents=True, exist_ok=True)

    val_df = pd.DataFrame([
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100.00,
         "counterparty": "Co", "location": "NY", "date": "2026-06-01",
         "source_txn_id": "DBFAIL001"},
    ])
    val_df.to_csv(staging_dir / "0.val", index=False)

    with open(staging_dir / "0.dbfail", "w") as f:
        f.write(json.dumps({
            "account_id": "ACC003", "customer_id": "CUST002", "amount": 200.00,
            "counterparty": "Co", "location": "LA", "date": "2026-06-02",
            "source_txn_id": "DBFAIL002",
        }) + "\n")

    result = await retry_upload(failed_id, seeded_session)
    assert result["accepted_count"] == 2

    txns = (await seeded_session.execute(
        select(Transaction).where(Transaction.upload_id == result["upload_id"])
    )).scalars().all()
    assert len(txns) == 2
    txn_srcs = {t.source_txn_id for t in txns}
    assert "DBFAIL001" in txn_srcs
    assert "DBFAIL002" in txn_srcs


@pytest.mark.asyncio
async def test_retry_skip_when_all_rows_are_dupes(seeded_session):
    from src.file_processor.service import retry_upload
    from src.core.models.transaction import Transaction
    from src.core.models.uploaded_files import UploadedFiles
    from src.bff.config import get_upload_dir
    from datetime import datetime, UTC
    from sqlalchemy import select
    import uuid
    import pandas as pd

    prev_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    prev_upload = UploadedFiles(
        id=prev_id, filename="all_dupes.csv", status="failed",
        total_rows=1, accepted_count=1, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(prev_upload)
    await seeded_session.flush()

    existing_tx = Transaction(
        upload_id=prev_id,
        account_id="ACC001",
        customer_id="CUST001",
        amount=100.00,
        counterparty="Co",
        city="New York", state="NY", country="US",
        date="2026-06-01",
        source_txn_id="DUP001",
        created_at=now,
        updated_at=now,
    )
    seeded_session.add(existing_tx)
    await seeded_session.commit()

    failed_id = str(uuid.uuid4())
    upload = UploadedFiles(
        id=failed_id, filename="all_dupes.csv", status="failed",
        total_rows=1, accepted_count=1, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    await seeded_session.commit()

    staging_dir = get_upload_dir() / "staging" / failed_id
    staging_dir.mkdir(parents=True, exist_ok=True)
    val_df = pd.DataFrame([
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100.00,
         "counterparty": "Co", "location": "NY", "date": "2026-06-01",
         "source_txn_id": "DUP001"},
    ])
    val_df.to_csv(staging_dir / "0.val", index=False)

    result = await retry_upload(failed_id, seeded_session)
    assert result["accepted_count"] == 0
    assert result["failed_count"] == 0


@pytest.mark.asyncio
async def test_retry_skips_dbfail_duplicates(seeded_session):
    from src.file_processor.service import retry_upload
    from src.core.models.transaction import Transaction
    from src.core.models.uploaded_files import UploadedFiles
    from src.bff.config import get_upload_dir
    from datetime import datetime, UTC
    from sqlalchemy import select
    import uuid
    import json
    import pandas as pd

    prev_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    prev_upload = UploadedFiles(
        id=prev_id, filename="dbfail_dedup.csv", status="failed",
        total_rows=1, accepted_count=1, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(prev_upload)
    await seeded_session.flush()
    existing_tx = Transaction(
        upload_id=prev_id, account_id="ACC001", customer_id="CUST001",
        amount=100.00, counterparty="Co", city="New York", state="NY", country="US", date="2026-06-01",
        source_txn_id="DBDUP001", created_at=now, updated_at=now,
    )
    seeded_session.add(existing_tx)
    await seeded_session.commit()

    failed_id = str(uuid.uuid4())
    upload = UploadedFiles(
        id=failed_id, filename="dbfail_dedup.csv", status="failed",
        total_rows=1, accepted_count=0, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    await seeded_session.commit()

    staging_dir = get_upload_dir() / "staging" / failed_id
    staging_dir.mkdir(parents=True, exist_ok=True)
    val_df = pd.DataFrame([
        {"account_id": "ACC002", "customer_id": "CUST001", "amount": 200.00,
         "counterparty": "Co", "location": "NY", "date": "2026-06-01",
         "source_txn_id": "DBDUP002"},
    ])
    val_df.to_csv(staging_dir / "0.val", index=False)
    with open(staging_dir / "0.dbfail", "w") as f:
        f.write(json.dumps({
            "account_id": "ACC001", "customer_id": "CUST001", "amount": 300.00,
            "counterparty": "Co", "location": "NY", "date": "2026-06-01",
            "source_txn_id": "DBDUP001",
        }) + "\n")

    result = await retry_upload(failed_id, seeded_session)
    assert result["accepted_count"] == 1
    txns = (await seeded_session.execute(
        select(Transaction).where(Transaction.upload_id == result["upload_id"])
    )).scalars().all()
    assert len(txns) == 1
    assert txns[0].source_txn_id == "DBDUP002"


@pytest.mark.asyncio
async def test_try_insert_rows_individual_also_fails_writes_dbfail(seeded_session):
    from src.file_processor.service import _try_insert_rows
    from src.core.models.uploaded_files import UploadedFiles
    from src.bff.config import get_upload_dir
    from datetime import datetime, UTC
    from sqlalchemy.exc import SQLAlchemyError
    from unittest.mock import patch
    import uuid

    now = datetime.now(UTC).isoformat()
    upload_id = str(uuid.uuid4())
    upload = UploadedFiles(
        id=upload_id, filename="indiv_fail.csv", status="processing",
        total_rows=1, uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    await seeded_session.flush()

    staging_dir = get_upload_dir() / "staging" / upload_id
    staging_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100.00,
         "counterparty": "Co", "city": "New York", "state": "NY", "country": "US", "date": "2026-06-01",
         "source_txn_id": "INDIVFAIL001"},
    ]

    call_count = 0
    original_flush = seeded_session.flush

    async def always_failing_flush():
        nonlocal call_count
        call_count += 1
        raise SQLAlchemyError("Flush always fails")

    with patch.object(seeded_session, "flush", always_failing_flush):
        inserted, failed = await _try_insert_rows(
            seeded_session, rows, upload_id, now, staging_dir, "0"
        )

    assert inserted == 0
    assert failed == 1
    dbfail_path = staging_dir / "0.dbfail"
    assert dbfail_path.exists()
    content = dbfail_path.read_text()
    assert "INDIVFAIL001" in content
