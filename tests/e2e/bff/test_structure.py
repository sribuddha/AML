import uuid
from datetime import datetime, UTC

import pandas as pd
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from src.bff.database import get_db
from src.bff.app import app
from src.core.models.transaction import Transaction
from src.core.models.uploaded_files import UploadedFiles
from src.file_processor.service import process_upload


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
        filename="test.csv",
        status="uploaded",
        total_rows=2,
        accepted_count=2,
        failed_count=0,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    seeded_session.add(upload)

    txns = [
        Transaction(
            id=str(uuid.uuid4()), upload_id=upload_id,
            account_id="ACC001", customer_id="CUST001",
            amount=1000.00, counterparty="Acme Corp",
            city="New York", state="NY", country="US",
            date="2026-05-01", source_txn_id="TXN001",
            created_at=now, updated_at=now,
        ),
        Transaction(
            id=str(uuid.uuid4()), upload_id=upload_id,
            account_id="ACC002", customer_id="CUST001",
            amount=25000.00, counterparty="Global Trading",
            city="London", state="", country="GB",
            date="2026-05-02", source_txn_id="TXN002",
            created_at=now, updated_at=now,
        ),
    ]
    seeded_session.add_all(txns)
    await seeded_session.commit()
    return upload_id


class TestApiStructure:
    def test_uploads_endpoint_returns_200_with_structure(self, client):
        resp = client.get("/api/uploads")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "page" in data
        assert "per_page" in data
        assert "total" in data

    def test_rules_endpoint_returns_200_with_structure(self, client):
        resp = client.get("/api/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "page" in data
        assert "per_page" in data
        assert "total" in data

    def test_create_rule_returns_200(self, client):
        resp = client.post("/api/rules", json={
            "name": "High Value Rule",
            "rules_json": [{"field": "amount", "operator": ">", "value": 10000}],
        })
        assert resp.status_code == 201

    def test_upload_transactions_returns_expected_keys(self, client, seeded_upload):
        resp = client.get(f"/api/uploads/{seeded_upload}/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        for item in data["items"]:
            assert "id" in item
            assert "account_id" in item
            assert "date" in item
            assert "amount" in item

    def test_upload_status_returns_status_fields(self, client, seeded_upload):
        resp = client.get(f"/api/uploads/{seeded_upload}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_uploads_list_returns_expected_fields(self, client, seeded_upload):
        resp = client.get("/api/uploads")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert "id" in item
            assert "filename" in item
            assert "status" in item
            assert "uploaded_at" in item
            assert "total_rows" in item
