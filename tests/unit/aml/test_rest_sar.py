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
    from src.aml_workflow.rest.sar import router
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_sars(seeded_session):
    now = datetime.now(UTC).isoformat()
    uid = str(uuid.uuid4())
    upload = UploadedFiles(
        id=uid, filename="t.csv", status="processing",
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    txns = []
    sars = []
    for i in range(3):
        txn = Transaction(
            id=str(uuid.uuid4()), upload_id=uid,
            account_id="ACC001", customer_id="CUST001",
            amount=1000.0 * (i + 1), counterparty=f"Payee_{i}",
            city="NYC", state="NY", country="US",
            date="2026-05-01", source_txn_id=f"TXN{i:04d}",
            created_at=now, updated_at=now,
        )
        seeded_session.add(txn)
        txns.append(txn)
        sar = SAR(
            id=str(uuid.uuid4()), transaction_id=txn.id, upload_id=uid,
            rule_id=str(uuid.uuid4()),
            content=f"SAR content {i}",
            status="pending_review",
            created_at=now, updated_at=now,
        )
        seeded_session.add(sar)
        sars.append(sar)
        vr = ValidationResult(
            id=str(uuid.uuid4()), transaction_id=txn.id, upload_id=uid,
            status="flagged", risk_level="high",
            flag_details={"rule-1": f"Rule {i}"},
            validated_at=now, created_at=now, updated_at=now,
        )
        seeded_session.add(vr)
    return uid, txns, sars


class TestSarRest:
    def test_list_sars(self, client, seeded_sars):
        resp = client.get("/api/sar")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_sars_filter_by_upload(self, client, seeded_sars):
        uid, _, _ = seeded_sars
        resp = client.get(f"/api/sar?upload_id={uid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    def test_list_sars_filter_by_status(self, client, seeded_sars):
        resp = client.get("/api/sar?status=pending_review")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3

    def test_get_sar_found(self, client, seeded_sars):
        _, _, sars = seeded_sars
        resp = client.get(f"/api/sar/{sars[0].id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sars[0].id
        assert "content" in data

    def test_get_sar_not_found(self, client):
        resp = client.get("/api/sar/nonexistent")
        assert resp.status_code == 404

    def test_review_sar_confirmed(self, client, seeded_sars):
        _, _, sars = seeded_sars
        resp = client.patch(f"/api/sar/{sars[0].id}/review", json={"action": "confirmed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmed"

    def test_review_sar_dismissed(self, client, seeded_sars):
        _, _, sars = seeded_sars
        resp = client.patch(f"/api/sar/{sars[0].id}/review", json={"action": "dismissed", "notes": "False positive"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "dismissed"
        assert data["review_notes"] == "False positive"

    def test_review_sar_not_found(self, client):
        resp = client.patch("/api/sar/nonexistent/review", json={"action": "confirmed"})
        assert resp.status_code == 404

    def test_review_sar_already_reviewed(self, client, seeded_sars):
        _, _, sars = seeded_sars
        client.patch(f"/api/sar/{sars[0].id}/review", json={"action": "confirmed"})
        resp = client.patch(f"/api/sar/{sars[0].id}/review", json={"action": "confirmed"})
        assert resp.status_code == 400

    def test_batch_review_confirmed(self, client, seeded_sars):
        _, _, sars = seeded_sars
        sar_ids = [s.id for s in sars]
        resp = client.post("/api/sar/batch-review", json={"sar_ids": sar_ids, "action": "confirmed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["reviewed"] == 3
        assert data["action"] == "confirmed"

    def test_batch_review_dismissed(self, client, seeded_sars):
        _, _, sars = seeded_sars
        sar_ids = [s.id for s in sars]
        resp = client.post("/api/sar/batch-review", json={"sar_ids": sar_ids, "action": "dismissed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["reviewed"] == 3

    def test_batch_review_invalid_action(self, client):
        resp = client.post("/api/sar/batch-review", json={"sar_ids": ["x"], "action": "invalid"})
        assert resp.status_code == 400

    def test_batch_review_empty_ids(self, client):
        resp = client.post("/api/sar/batch-review", json={"sar_ids": [], "action": "confirmed"})
        assert resp.status_code == 400

    def test_batch_review_no_pending_sars(self, client):
        resp = client.post("/api/sar/batch-review", json={"sar_ids": ["nonexistent"], "action": "confirmed"})
        assert resp.status_code == 404
