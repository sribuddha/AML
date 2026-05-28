import uuid
from datetime import datetime, UTC

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.models.sar import SAR
from src.core.models.validation_result import ValidationResult
from src.bff.database import get_db
from src.core.models.transaction import Transaction
from src.core.models.uploaded_files import UploadedFiles


@pytest.fixture
def client(seeded_session):
    app = FastAPI()
    from src.bff.routes.compliance import router
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_pending_sar(seeded_session):
    now = datetime.now(UTC).isoformat()
    uid = str(uuid.uuid4())
    upload = UploadedFiles(
        id=uid, filename="t.csv", status="processing",
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    txn = Transaction(
        id=str(uuid.uuid4()), upload_id=uid,
        account_id="ACC001", customer_id="CUST001",
        amount=15000.0, counterparty="Offshore Ltd",
        city="Cayman", state="", country="KY",
        date="2026-05-15", source_txn_id="TXN001",
        created_at=now, updated_at=now,
    )
    seeded_session.add(txn)
    vr = ValidationResult(
        id=str(uuid.uuid4()), transaction_id=txn.id, upload_id=uid,
        status="flagged", risk_level="high",
        flag_details={"rule-1": "High Value"},
        validated_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(vr)
    sar = SAR(
        id=str(uuid.uuid4()), transaction_id=txn.id, upload_id=uid,
        rule_id=str(uuid.uuid4()),
        content="Suspicious: high-value offshore transfer.",
        status="pending_review",
        created_at=now, updated_at=now,
    )
    seeded_session.add(sar)
    return uid


class TestComplianceRoutes:
    def test_list_pending_sars(self, client, seeded_pending_sar):
        resp = client.get("/api/sar/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["sar_status"] == "pending_review"
            assert "sar_id" in item
            assert "sar_content" in item

    def test_filter_by_upload_id(self, client, seeded_pending_sar):
        uid = seeded_pending_sar
        resp = client.get(f"/api/sar/pending?upload_id={uid}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["upload_id"] == uid

    def test_filter_by_customer_id(self, client, seeded_pending_sar):
        resp = client.get("/api/sar/pending?customer_id=CUST001")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) >= 1

    def test_pagination(self, client, seeded_pending_sar):
        resp = client.get("/api/sar/pending?page=1&per_page=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["per_page"] == 10

    def test_no_results(self, client):
        resp = client.get("/api/sar/pending?upload_id=NONEXISTENT")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
