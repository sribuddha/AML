import uuid
from datetime import datetime, UTC

import pytest
import pytest_asyncio

from src.aml_workflow.models.validation_result import ValidationResult
from src.file_processor.models import UploadedFiles, Transaction


@pytest_asyncio.fixture
async def seeded_validation_data(seeded_session):
    now = datetime.now(UTC).isoformat()
    upload_id = str(uuid.uuid4())
    upload = UploadedFiles(
        id=upload_id, filename="val_test.csv", status="processing",
        total_rows=2, accepted_count=2, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)

    txns = []
    for i in range(2):
        txn = Transaction(
            id=str(uuid.uuid4()), upload_id=upload_id,
            account_id="ACC001", customer_id="CUST001",
            amount=100.0 + i, counterparty=f"ValPayee_{i}",
            city="New York", state="NY", country="US",
            date="2026-05-01", source_txn_id=f"VALTXN{i:04d}",
            created_at=now, updated_at=now,
        )
        seeded_session.add(txn)
        txns.append(txn)

    results = []
    for txn in txns:
        vr = ValidationResult(
            id=str(uuid.uuid4()), upload_id=upload_id,
            transaction_id=txn.id, status="clean",
            flag_details=None, validated_at=now,
            created_at=now, updated_at=now,
        )
        seeded_session.add(vr)
        results.append(vr)

    flagged_txn = Transaction(
        id=str(uuid.uuid4()), upload_id=upload_id,
        account_id="ACC001", customer_id="CUST001",
        amount=50000.0, counterparty="Flagged Co",
        city="Unknown", state="", country="",
        date="2026-05-15", source_txn_id="VALTXNflag",
        created_at=now, updated_at=now,
    )
    seeded_session.add(flagged_txn)
    flagged_vr = ValidationResult(
        id=str(uuid.uuid4()), upload_id=upload_id,
        transaction_id=flagged_txn.id, status="flagged",
        flag_details={"rule-1": "High Value Check"},
        validated_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(flagged_vr)
    txns.append(flagged_txn)
    results.append(flagged_vr)

    await seeded_session.commit()
    return upload_id, txns, results


class TestValidationAPI:
    async def test_get_validation_summary(self, client, seeded_validation_data):
        upload_id, _, _ = seeded_validation_data
        resp = await client.get(f"/api/uploads/{upload_id}/validation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["upload_id"] == upload_id
        assert data["clean_count"] >= 2
        assert data["flagged_count"] >= 1
        assert data["total_count"] >= 3

    async def test_get_validation_flagged_detail(self, client, seeded_validation_data):
        upload_id, _, _ = seeded_validation_data
        resp = await client.get(f"/api/uploads/{upload_id}/validation?status=flagged")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["status"] == "flagged"

    async def test_get_validation_returns_404(self, client):
        resp = await client.get(f"/api/uploads/{uuid.uuid4()}/validation")
        assert resp.status_code == 404

    async def test_get_validation_by_date(self, client, seeded_validation_data):
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        resp = await client.get(f"/api/validation/date/{today}")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1
        seen_ids = {item["upload_id"] for item in items}
        assert seeded_validation_data[0] in seen_ids

    async def test_get_validation_by_transaction(self, client, seeded_validation_data):
        _, txns, _ = seeded_validation_data
        src_id = txns[0].source_txn_id
        resp = await client.get(f"/api/validation/transaction/{src_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "clean"

    async def test_get_validation_by_transaction_returns_404(self, client):
        resp = await client.get(f"/api/validation/transaction/{uuid.uuid4()}")
        assert resp.status_code == 404
