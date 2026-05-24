import uuid
from datetime import datetime, UTC

import pytest
import pytest_asyncio

from src.file_processor.models import UploadedFiles, Transaction, RejectedRecord


@pytest_asyncio.fixture
async def seeded_read_data(seeded_session):
    now = datetime.now(UTC).isoformat()
    upload_id = str(uuid.uuid4())
    upload = UploadedFiles(
        id=upload_id,
        filename="test.csv",
        status="completed",
        total_rows=3,
        accepted_count=3,
        failed_count=0,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    seeded_session.add(upload)

    txns = []
    for i in range(3):
        txn = Transaction(
            id=str(uuid.uuid4()),
            upload_id=upload_id,
            account_id="ACC001",
            customer_id="CUST001",
            amount=100.0 + i,
            counterparty=f"Payee_{i}",
            city="New York",
            state="NY",
            country="US",
            date="2026-05-01",
            source_txn_id=f"RDTXN{i:04d}",
            created_at=now,
            updated_at=now,
        )
        seeded_session.add(txn)
        txns.append(txn)

    rejected = RejectedRecord(
        id=str(uuid.uuid4()),
        upload_id=upload_id,
        row_index=0,
        raw_data='{"account_id": "ACC999"}',
        reasons='["Unknown account"]',
        created_at=now,
        updated_at=now,
    )
    seeded_session.add(rejected)
    await seeded_session.commit()
    return upload_id, txns, rejected


class TestReadAPI:
    async def test_get_upload_returns_200(self, client, seeded_read_data):
        upload_id, _, _ = seeded_read_data
        resp = await client.get(f"/api/uploads/{upload_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == upload_id
        assert data["filename"] == "test.csv"
        assert data["status"] == "completed"

    async def test_get_upload_returns_404(self, client):
        resp = await client.get(f"/api/uploads/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_list_transactions_returns_200(self, client, seeded_read_data):
        upload_id, _, _ = seeded_read_data
        resp = await client.get(f"/api/uploads/{upload_id}/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] == 3

    async def test_list_transactions_returns_404(self, client):
        resp = await client.get(f"/api/uploads/{uuid.uuid4()}/transactions")
        assert resp.status_code == 404

    async def test_get_transaction_returns_200(self, client, seeded_read_data):
        _, txns, _ = seeded_read_data
        txn_id = txns[0].id
        resp = await client.get(f"/api/transactions/{txn_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == txn_id

    async def test_get_transaction_returns_404(self, client):
        resp = await client.get(f"/api/transactions/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_list_rejected_returns_paginated(self, client, seeded_read_data):
        upload_id, _, _ = seeded_read_data
        resp = await client.get(f"/api/uploads/{upload_id}/rejected")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert len(data["items"]) >= 1
        assert "raw_data" in data["items"][0]
        assert "reasons" in data["items"][0]
