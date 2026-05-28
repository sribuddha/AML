import uuid
from datetime import datetime, UTC

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.models.validation_result import ValidationResult
from src.bff.database import get_db
from src.core.models.transaction import Transaction
from src.core.models.uploaded_files import UploadedFiles


@pytest.fixture
def client(seeded_session):
    app = FastAPI()
    from src.aml_workflow.rest.validation import router
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_validation(seeded_session):
    now = datetime.now(UTC).isoformat()
    uid = str(uuid.uuid4())
    upload = UploadedFiles(
        id=uid, filename="t.csv", status="processing",
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    txns = []
    for i in range(4):
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
        vrs = []
        status = "clean" if i < 2 else "flagged"
        vr = ValidationResult(
            id=str(uuid.uuid4()), transaction_id=txn.id, upload_id=uid,
            status=status, risk_level=status,
            flag_details={"r-1": "Rule A"} if status == "flagged" else None,
            validated_at=now, created_at=now, updated_at=now,
        )
        vrs.append(vr)
        seeded_session.add(vr)
    return uid, txns


class TestValidationRest:
    def test_get_validation_summary(self, client, seeded_validation):
        uid, _ = seeded_validation
        resp = client.get(f"/api/uploads/{uid}/validation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["clean_count"] == 2
        assert data["flagged_count"] == 2
        assert data["total_count"] == 4

    def test_get_validation_summary_upload_not_found(self, client):
        resp = client.get("/api/uploads/nonexistent/validation")
        assert resp.status_code == 404

    def test_get_validation_filtered_flagged(self, client, seeded_validation):
        uid, _ = seeded_validation
        resp = client.get(f"/api/uploads/{uid}/validation?status=flagged")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(i["status"] == "flagged" for i in data["items"])

    def test_get_validation_filtered_clean(self, client, seeded_validation):
        uid, _ = seeded_validation
        resp = client.get(f"/api/uploads/{uid}/validation?status=clean")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(i["status"] == "clean" for i in data["items"])

    def test_get_validation_paginated(self, client, seeded_validation):
        uid, _ = seeded_validation
        resp = client.get(f"/api/uploads/{uid}/validation?status=flagged&page=1&per_page=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["per_page"] == 1
        assert len(data["items"]) == 1

    def test_get_validation_by_date(self, client, seeded_validation):
        from datetime import datetime, UTC
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        resp = client.get(f"/api/validation/date/{today}")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1
        for item in items:
            assert "upload_id" in item
            assert "clean_count" in item
            assert "flagged_count" in item

    def test_get_validation_by_date_no_results(self, client):
        resp = client.get("/api/validation/date/2099-01-01")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_validation_by_transaction_found(self, client, seeded_validation):
        _, txns = seeded_validation
        resp = client.get(f"/api/validation/transaction/{txns[0].source_txn_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("clean", "flagged")
        assert "upload_id" in data

    def test_get_validation_by_transaction_not_found(self, client):
        resp = client.get("/api/validation/transaction/NONEXISTENT")
        assert resp.status_code == 404
