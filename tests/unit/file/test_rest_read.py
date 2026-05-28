import uuid
import json
from datetime import datetime, UTC

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.bff.database import get_db
from src.file_processor.models import RejectedRecord
from src.core.models.transaction import Transaction
from src.core.models.uploaded_files import UploadedFiles


@pytest.fixture
def client(seeded_session):
    app = FastAPI()
    from src.file_processor.rest.read import router
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_read_data(seeded_session):
    now = datetime.now(UTC).isoformat()
    uid = str(uuid.uuid4())
    upload = UploadedFiles(
        id=uid, filename="t.csv", status="completed",
        total_rows=10, accepted_count=8, failed_count=2,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    txns = []
    for i in range(3):
        txn = Transaction(
            id=str(uuid.uuid4()), upload_id=uid,
            account_id="ACC001", customer_id="CUST001",
            amount=100.0 * (i + 1), counterparty=f"Payee_{i}",
            city="NYC", state="NY", country="US",
            date="2026-05-01", source_txn_id=f"TXN{i:04d}",
            created_at=now, updated_at=now,
        )
        seeded_session.add(txn)
        txns.append(txn)
    rejected = RejectedRecord(
        id=str(uuid.uuid4()), upload_id=uid, row_index=5,
        raw_data=json.dumps({"account_id": "BAD"}), reasons=json.dumps(["Invalid account"]),
        created_at=now,
    )
    seeded_session.add(rejected)
    return uid, txns


class TestReadRest:
    def test_list_uploads(self, client, seeded_read_data):
        resp = client.get("/api/uploads")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert "id" in item
            assert "filename" in item
            assert "status" in item

    def test_list_uploads_paginated(self, client, seeded_read_data):
        resp = client.get("/api/uploads?page=1&per_page=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["per_page"] == 10

    def test_get_upload_found(self, client, seeded_read_data):
        uid, _ = seeded_read_data
        resp = client.get(f"/api/uploads/{uid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == uid
        assert data["total_rows"] == 10
        assert data["accepted_count"] == 8
        assert data["failed_count"] == 2

    def test_get_upload_not_found(self, client):
        resp = client.get("/api/uploads/nonexistent")
        assert resp.status_code == 404

    def test_list_transactions(self, client, seeded_read_data):
        uid, _ = seeded_read_data
        resp = client.get(f"/api/uploads/{uid}/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_transactions_upload_not_found(self, client):
        resp = client.get("/api/uploads/nonexistent/transactions")
        assert resp.status_code == 404

    def test_get_transaction_found(self, client, seeded_read_data):
        _, txns = seeded_read_data
        resp = client.get(f"/api/transactions/{txns[0].id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == txns[0].id
        assert data["amount"] == 100.0

    def test_get_transaction_not_found(self, client):
        resp = client.get("/api/transactions/nonexistent")
        assert resp.status_code == 404

    def test_list_rejected_records(self, client, seeded_read_data):
        uid, _ = seeded_read_data
        resp = client.get(f"/api/uploads/{uid}/rejected")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["row_index"] == 5
        assert item["raw_data"] == {"account_id": "BAD"}
        assert item["reasons"] == ["Invalid account"]

    def test_list_rejected_records_upload_not_found(self, client):
        resp = client.get("/api/uploads/nonexistent/rejected")
        assert resp.status_code == 404

    def test_rejected_raw_data_bad_json(self, client, seeded_session):
        now = datetime.now(UTC).isoformat()
        uid = str(uuid.uuid4())
        upload = UploadedFiles(
            id=uid, filename="t.csv", status="completed",
            uploaded_at=now, created_at=now, updated_at=now,
        )
        seeded_session.add(upload)
        bad = RejectedRecord(
            id=str(uuid.uuid4()), upload_id=uid, row_index=1,
            raw_data="not valid json at all",
            reasons=json.dumps(["test"]),
            created_at=now,
        )
        seeded_session.add(bad)
        resp = client.get(f"/api/uploads/{uid}/rejected")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["raw_data"] == {"raw": "not valid json at all"}

    def test_rejected_reasons_bad_json(self, client, seeded_session):
        now = datetime.now(UTC).isoformat()
        uid = str(uuid.uuid4())
        upload = UploadedFiles(
            id=uid, filename="t.csv", status="completed",
            uploaded_at=now, created_at=now, updated_at=now,
        )
        seeded_session.add(upload)
        bad = RejectedRecord(
            id=str(uuid.uuid4()), upload_id=uid, row_index=2,
            raw_data=json.dumps({"k": "v"}),
            reasons="[invalid json",
            created_at=now,
        )
        seeded_session.add(bad)
        resp = client.get(f"/api/uploads/{uid}/rejected")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["reasons"] == ["[invalid json"]
