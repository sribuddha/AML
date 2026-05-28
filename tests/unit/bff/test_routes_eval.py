import json
import uuid
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.models.sar import SAR
from src.core.models.validation_result import ValidationResult
from src.bff.database import get_db
from src.bff.routes.eval import _load_eval_entries
from src.core.models.transaction import Transaction
from src.core.models.uploaded_files import UploadedFiles


@pytest.fixture
def client(seeded_session):
    app = FastAPI()
    from src.bff.routes.eval import router
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_eval_data(seeded_session, tmp_path):
    now = datetime.now(UTC).isoformat()
    uid = str(uuid.uuid4())

    eval_file = tmp_path / "test.eval"
    eval_file.write_text(
        json.dumps({"source_txn_id": "TXN001", "scenario": "high_value", "expected_escalate": True}) + "\n" +
        json.dumps({"source_txn_id": "TXN002", "scenario": "structuring", "expected_escalate": True}) + "\n"
    )

    upload = UploadedFiles(
        id=uid, filename="t.csv", status="completed",
        total_rows=5, accepted_count=5, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
        eval_file=str(eval_file),
    )
    seeded_session.add(upload)

    txns = []
    for i in range(2):
        txn = Transaction(
            id=str(uuid.uuid4()), upload_id=uid,
            account_id="ACC001", customer_id="CUST001",
            amount=50000.0, counterparty=f"Payee_{i}",
            city="NYC", state="NY", country="US",
            date="2026-05-01", source_txn_id=f"TXN00{i+1}",
            created_at=now, updated_at=now,
        )
        seeded_session.add(txn)
        txns.append(txn)

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
            content=f"SAR for {txn.source_txn_id}",
            status="pending_review",
            created_at=now, updated_at=now,
        )
        seeded_session.add(sar)

    return uid, txns, eval_file


class TestLoadEvalEntries:
    def test_load_eval_file(self, tmp_path):
        f = tmp_path / "test.eval"
        f.write_text(json.dumps({"source_txn_id": "T1", "scenario": "sv"}) + "\n")
        entries = _load_eval_entries(str(f))
        assert len(entries) == 1
        assert entries[0]["source_txn_id"] == "T1"

    def test_load_manifest_json(self, tmp_path):
        f = tmp_path / "test.manifest.json"
        f.write_text(json.dumps({"TXN001": "high_value", "TXN002": "structuring"}))
        entries = _load_eval_entries(str(f))
        assert len(entries) == 2
        assert entries[0]["source_txn_id"] == "TXN001"
        assert entries[0]["expected_escalate"] is True

    def test_load_empty_manifest_json(self, tmp_path):
        f = tmp_path / "test.manifest.json"
        f.write_text("{}")
        entries = _load_eval_entries(str(f))
        assert entries == []

    def test_load_file_not_found(self):
        entries = _load_eval_entries("/nonexistent/file.eval")
        assert entries == []

    def test_load_empty_lines(self, tmp_path):
        f = tmp_path / "test.eval"
        f.write_text("\n\n")
        entries = _load_eval_entries(str(f))
        assert entries == []


class TestEvalEndpoint:
    def test_eval_upload_not_found(self, client):
        resp = client.post("/api/uploads/nonexistent/eval")
        assert resp.status_code == 404

    def test_eval_empty_file(self, client, seeded_session, tmp_path):
        uid = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        ef = tmp_path / "empty.eval"
        ef.write_text("\n\n")
        upload = UploadedFiles(
            id=uid, filename="t.csv", status="completed",
            uploaded_at=now, created_at=now, updated_at=now,
            eval_file=str(ef),
        )
        seeded_session.add(upload)
        resp = client.post(f"/api/uploads/{uid}/eval")
        assert resp.status_code == 400
        assert "empty or not found" in resp.json()["detail"]

    def test_eval_upload_no_eval_file(self, client, seeded_session):
        uid = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        upload = UploadedFiles(
            id=uid, filename="t.csv", status="completed",
            uploaded_at=now, created_at=now, updated_at=now,
        )
        seeded_session.add(upload)

        resp = client.post(f"/api/uploads/{uid}/eval")
        assert resp.status_code == 400
        assert "No eval data" in resp.json()["detail"]

    def test_eval_success(self, client, seeded_eval_data):
        uid, _, _ = seeded_eval_data
        resp = client.post(f"/api/uploads/{uid}/eval")
        assert resp.status_code == 200
        data = resp.json()
        assert data["upload_id"] == uid
        assert data["total_transactions"] == 2
        assert data["total_anomalous"] == 2
        assert data["total_flagged"] == 2
        assert len(data["pattern_metrics"]) > 0
        assert len(data["hallucination_results"]) == 2
        assert len(data["completeness_results"]) == 2

    def test_eval_pattern_metrics(self, client, seeded_eval_data):
        uid, _, _ = seeded_eval_data
        resp = client.post(f"/api/uploads/{uid}/eval")
        data = resp.json()
        for pm in data["pattern_metrics"]:
            assert "pattern" in pm
            assert "precision" in pm
            assert "recall" in pm
            assert "f1" in pm

    def test_eval_skip_missing_txn(self, client, seeded_session, tmp_path):
        now = datetime.now(UTC).isoformat()
        uid = str(uuid.uuid4())
        ef = tmp_path / "test.eval"
        ef.write_text(
            json.dumps({"source_txn_id": "EXISTS", "scenario": "sv", "expected_escalate": True}) + "\n" +
            json.dumps({"source_txn_id": "MISSING", "scenario": "sv", "expected_escalate": False}) + "\n"
        )
        upload = UploadedFiles(
            id=uid, filename="t.csv", status="completed",
            total_rows=1, accepted_count=1, failed_count=0,
            uploaded_at=now, created_at=now, updated_at=now,
            eval_file=str(ef),
        )
        seeded_session.add(upload)
        txn = Transaction(
            id=str(uuid.uuid4()), upload_id=uid,
            account_id="ACC001", customer_id="CUST001",
            amount=100.0, counterparty="Payee",
            city="NYC", state="NY", country="US",
            date="2026-05-01", source_txn_id="EXISTS",
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
            rule_id=str(uuid.uuid4()), content="SAR for EXISTS",
            status="pending_review", created_at=now, updated_at=now,
        )
        seeded_session.add(sar)
        resp = client.post(f"/api/uploads/{uid}/eval")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_transactions"] == 1

    def test_eval_skip_missing_vr(self, client, seeded_session, tmp_path):
        now = datetime.now(UTC).isoformat()
        uid = str(uuid.uuid4())
        ef = tmp_path / "test.eval"
        ef.write_text(
            json.dumps({"source_txn_id": "T1", "scenario": "sv", "expected_escalate": True}) + "\n" +
            json.dumps({"source_txn_id": "T2", "scenario": "sv", "expected_escalate": False}) + "\n"
        )
        upload = UploadedFiles(
            id=uid, filename="t.csv", status="completed",
            uploaded_at=now, created_at=now, updated_at=now,
            eval_file=str(ef),
        )
        seeded_session.add(upload)
        t1 = Transaction(
            id=str(uuid.uuid4()), upload_id=uid,
            account_id="ACC001", customer_id="CUST001",
            amount=100.0, counterparty="P1",
            city="NYC", state="NY", country="US",
            date="2026-05-01", source_txn_id="T1",
            created_at=now, updated_at=now,
        )
        seeded_session.add(t1)
        t2 = Transaction(
            id=str(uuid.uuid4()), upload_id=uid,
            account_id="ACC001", customer_id="CUST001",
            amount=200.0, counterparty="P2",
            city="NYC", state="NY", country="US",
            date="2026-05-02", source_txn_id="T2",
            created_at=now, updated_at=now,
        )
        seeded_session.add(t2)
        vr = ValidationResult(
            id=str(uuid.uuid4()), transaction_id=t1.id, upload_id=uid,
            status="flagged", risk_level="high",
            flag_details={"r": "v"}, validated_at=now, created_at=now, updated_at=now,
        )
        seeded_session.add(vr)
        sar = SAR(
            id=str(uuid.uuid4()), transaction_id=t1.id, upload_id=uid,
            rule_id=str(uuid.uuid4()), content="SAR", status="pending_review",
            created_at=now, updated_at=now,
        )
        seeded_session.add(sar)
        resp = client.post(f"/api/uploads/{uid}/eval")
        assert resp.status_code == 200

    def test_eval_skip_sar_missing_txn(self, client, seeded_session, tmp_path):
        now = datetime.now(UTC).isoformat()
        uid = str(uuid.uuid4())
        ef = tmp_path / "test.eval"
        ef.write_text(
            json.dumps({"source_txn_id": "T1", "scenario": "sv", "expected_escalate": True}) + "\n"
        )
        upload = UploadedFiles(
            id=uid, filename="t.csv", status="completed",
            uploaded_at=now, created_at=now, updated_at=now,
            eval_file=str(ef),
        )
        seeded_session.add(upload)
        txn = Transaction(
            id=str(uuid.uuid4()), upload_id=uid,
            account_id="ACC001", customer_id="CUST001",
            amount=100.0, counterparty="P1",
            city="NYC", state="NY", country="US",
            date="2026-05-01", source_txn_id="T1",
            created_at=now, updated_at=now,
        )
        seeded_session.add(txn)
        vr = ValidationResult(
            id=str(uuid.uuid4()), transaction_id=txn.id, upload_id=uid,
            status="flagged", risk_level="high",
            flag_details={"r": "v"}, validated_at=now, created_at=now, updated_at=now,
        )
        seeded_session.add(vr)
        sar = SAR(
            id=str(uuid.uuid4()), transaction_id=str(uuid.uuid4()), upload_id=uid,
            rule_id=str(uuid.uuid4()), content="SAR orphan", status="pending_review",
            created_at=now, updated_at=now,
        )
        seeded_session.add(sar)
        resp = client.post(f"/api/uploads/{uid}/eval")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["hallucination_results"]) == 0
        assert len(data["completeness_results"]) == 0
