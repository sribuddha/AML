import uuid
from datetime import datetime, UTC

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.bff.database import get_db
from src.bff.app import app
from src.core.models.transaction import Transaction
from src.core.models.uploaded_files import UploadedFiles
from src.core.models.sar import SAR


@pytest.fixture
def client(seeded_session):
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def upload_id():
    return str(uuid.uuid4())


@pytest_asyncio.fixture
async def seeded_upload(seeded_session, upload_id):
    now = datetime.now(UTC).isoformat()
    upload = UploadedFiles(
        id=upload_id,
        filename="txns.csv",
        status="completed",
        total_rows=20,
        accepted_count=20,
        failed_count=0,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    seeded_session.add(upload)

    txns = []
    for i in range(20):
        txns.append(Transaction(
            id=str(uuid.uuid4()), upload_id=upload_id,
            account_id="ACC001", customer_id="CUST001",
            amount=100.0 + i, counterparty=f"Payee_{i}",
            city="New York", state="NY", country="US",
            date="2026-05-01", source_txn_id=f"TXN{i:04d}",
            created_at=now, updated_at=now,
        ))
    seeded_session.add_all(txns)

    sars = []
    for i in range(3):
        txn_id = txns[i].id
        sar = SAR(
            id=str(uuid.uuid4()), transaction_id=txn_id,
            upload_id=upload_id, content=f"SAR content {i}",
            status="pending_review", created_at=now, updated_at=now,
        )
        sars.append(sar)
    seeded_session.add_all(sars)
    await seeded_session.commit()
    return upload_id, txns, sars


class TestReadEndpoints:
    def test_list_transactions_paginated(self, client, seeded_upload):
        upload_id, _, _ = seeded_upload
        resp = client.get(f"/api/uploads/{upload_id}/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) <= 50

    def test_transactions_pagination_offset(self, client, seeded_upload):
        upload_id, _, _ = seeded_upload
        resp = client.get(f"/api/uploads/{upload_id}/transactions?page=2&per_page=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["page"] == 2
        assert data["per_page"] == 5

    def test_sar_reports_returns_expected_structure(self, client, seeded_upload):
        resp = client.get("/api/sar")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        if data["items"]:
            for item in data["items"]:
                assert "id" in item
                assert "content" in item
                assert "status" in item
