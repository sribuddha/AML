import uuid
from datetime import datetime, UTC

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.aml_workflow.models.upload_status import UploadStatus
from src.bff.database import get_db
from src.core.models.uploaded_files import UploadedFiles


@pytest.fixture
def client(seeded_session):
    app = FastAPI()
    from src.aml_workflow.rest.audit import router
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_status(seeded_session):
    now = datetime.now(UTC).isoformat()
    uid = str(uuid.uuid4())
    upload = UploadedFiles(
        id=uid, filename="t.csv", status="processing",
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    entries = [
        UploadStatus(upload_id=uid, status="uploaded", actor="system", created_at=now),
        UploadStatus(upload_id=uid, status="processing", actor="system", created_at=now),
    ]
    seeded_session.add_all(entries)
    return uid


class TestAuditRest:
    def test_list_status_found(self, client, seeded_status):
        resp = client.get(f"/api/uploads/{seeded_status}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        for item in data["items"]:
            assert "id" in item
            assert "status" in item
            assert "actor" in item

    def test_list_status_not_found(self, client):
        resp = client.get("/api/uploads/nonexistent/status")
        assert resp.status_code == 404

    def test_list_status_paginated(self, client, seeded_status):
        resp = client.get(f"/api/uploads/{seeded_status}/status?page=1&per_page=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["per_page"] == 1
        assert len(data["items"]) == 1
