import uuid
from datetime import datetime, UTC

import pytest
import pytest_asyncio

from src.aml_workflow.models.sar import SAR
from src.file_processor.models import UploadedFiles, Transaction


@pytest_asyncio.fixture
async def seeded_sar_data(seeded_session):
    now = datetime.now(UTC).isoformat()
    upload_id = str(uuid.uuid4())
    upload = UploadedFiles(
        id=upload_id,
        filename="sar_test.csv",
        status="processing",
        total_rows=2,
        accepted_count=2,
        failed_count=0,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    seeded_session.add(upload)

    txn = Transaction(
        id=str(uuid.uuid4()),
        upload_id=upload_id,
        account_id="ACC001",
        customer_id="CUST001",
        amount=50000.0,
        counterparty="Offshore Ltd",
        city="George Town",
        state="",
        country="KY",
        date="2026-05-15",
        source_txn_id="SARTXN001",
        created_at=now,
        updated_at=now,
    )
    seeded_session.add(txn)

    sar = SAR(
        id=str(uuid.uuid4()),
        transaction_id=txn.id,
        upload_id=upload_id,
        rule_id=None,
        content="High-value transfer flagged for review.",
        status="pending_review",
        created_at=now,
        updated_at=now,
    )
    seeded_session.add(sar)
    await seeded_session.commit()
    return upload_id, txn, sar


@pytest_asyncio.fixture
async def seeded_reviewed_sar(seeded_session):
    now = datetime.now(UTC).isoformat()
    upload_id = str(uuid.uuid4())
    upload = UploadedFiles(
        id=upload_id, filename="already.csv", status="processing",
        total_rows=1, accepted_count=1, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    txn = Transaction(
        id=str(uuid.uuid4()), upload_id=upload_id,
        account_id="ACC001", customer_id="CUST001",
        amount=100.0, counterparty="Test",
        city="NYC", state="NY", country="US",
        date="2026-05-01", source_txn_id="REVTXN",
        created_at=now, updated_at=now,
    )
    seeded_session.add(txn)
    sar = SAR(
        id=str(uuid.uuid4()), transaction_id=txn.id,
        upload_id=upload_id, content="Already reviewed.",
        status="confirmed", created_at=now, updated_at=now,
        reviewed_at=now, review_notes="Approved.",
    )
    seeded_session.add(sar)
    await seeded_session.commit()
    return sar


class TestSarAPI:
    async def test_get_sar_returns_200(self, client, seeded_sar_data):
        _, _, sar = seeded_sar_data
        resp = await client.get(f"/api/sar/{sar.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sar.id
        assert data["content"] == sar.content
        assert data["status"] == "pending_review"

    async def test_get_sar_returns_404(self, client):
        resp = await client.get(f"/api/sar/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_review_sar_confirmed(self, client, seeded_sar_data):
        _, _, sar = seeded_sar_data
        resp = await client.patch(f"/api/sar/{sar.id}/review", json={"action": "confirmed", "notes": "Looks legit"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["review_notes"] == "Looks legit"

    async def test_review_sar_dismissed(self, client, seeded_sar_data):
        _, _, sar = seeded_sar_data
        resp = await client.patch(f"/api/sar/{sar.id}/review", json={"action": "dismissed", "notes": "False positive"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "dismissed"
        assert data["review_notes"] == "False positive"

    async def test_review_sar_returns_404(self, client):
        resp = await client.patch(f"/api/sar/{uuid.uuid4()}/review", json={"action": "confirmed"})
        assert resp.status_code == 404

    async def test_review_sar_returns_400_already_reviewed(self, client, seeded_reviewed_sar):
        sar = seeded_reviewed_sar
        resp = await client.patch(f"/api/sar/{sar.id}/review", json={"action": "confirmed"})
        assert resp.status_code == 400
        assert "already" in resp.json()["detail"].lower()

    async def test_list_sar_with_upload_id_filter(self, client, seeded_sar_data):
        upload_id, _, _ = seeded_sar_data
        resp = await client.get(f"/api/sar?upload_id={upload_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["upload_id"] == upload_id

    async def test_list_sar_with_status_filter(self, client, seeded_sar_data, seeded_reviewed_sar):
        resp = await client.get("/api/sar?status=pending_review")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["status"] == "pending_review"
