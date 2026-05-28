import uuid
from datetime import datetime, UTC

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.bff.database import get_db
from src.core.models.uploaded_files import UploadedFiles
from src.core.models.validation_result import ValidationResult


@pytest.fixture
def client(seeded_session):
    app = FastAPI()
    from src.file_processor.rest.reprocess import router
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c


def _create_upload(seeded_session, status):
    now = datetime.now(UTC).isoformat()
    uid = str(uuid.uuid4())
    u = UploadedFiles(
        id=uid, filename="t.csv", status=status,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(u)
    return uid


class TestReprocessRest:
    def test_reprocess_not_found(self, client):
        resp = client.post("/api/uploads/nonexistent/reprocess")
        assert resp.status_code == 404

    def test_reprocess_complete_returns_400(self, client, seeded_session):
        uid = _create_upload(seeded_session, "complete")
        resp = client.post(f"/api/uploads/{uid}/reprocess")
        assert resp.status_code == 400
        assert "already complete" in resp.json()["detail"].lower()

    def test_reprocess_unknown_status(self, client, seeded_session):
        uid = _create_upload(seeded_session, "failed")
        resp = client.post(f"/api/uploads/{uid}/reprocess")
        assert resp.status_code == 400
        assert "unknown status" in resp.json()["detail"].lower()

    def test_reprocess_uploaded_status(self, client, seeded_session):
        uid = _create_upload(seeded_session, "uploaded")
        resp = client.post(f"/api/uploads/{uid}/reprocess")
        assert resp.status_code == 202

    def test_reprocess_bad_heartbeat(self, client, seeded_session):
        uid = _create_upload(seeded_session, "processing")
        now = datetime.now(UTC).isoformat()
        vr = ValidationResult(
            id=str(uuid.uuid4()), transaction_id=str(uuid.uuid4()),
            upload_id=uid, status="flagged",
            flag_details={}, validated_at=now,
            updated_at="not-a-valid-timestamp",
            created_at=now,
        )
        seeded_session.add(vr)
        resp = client.post(f"/api/uploads/{uid}/reprocess")
        assert resp.status_code == 202
