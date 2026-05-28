import uuid
from datetime import datetime, UTC

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.bff.database import get_db
from src.core.models.uploaded_files import UploadedFiles


@pytest.fixture
def client(seeded_session):
    app = FastAPI()
    from src.bff.routes.operations import router
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_upload(seeded_session):
    now = datetime.now(UTC).isoformat()
    uid = str(uuid.uuid4())
    upload = UploadedFiles(
        id=uid,
        filename="test.csv",
        status="completed",
        total_rows=100,
        accepted_count=95,
        failed_count=5,
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    seeded_session.add(upload)
    return uid


class TestOperationsRoutes:
    def test_search_uploads_by_id(self, client, seeded_upload):
        partial = seeded_upload[:8]
        resp = client.get(f"/api/uploads/search?upload_id={partial}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(u["id"] == seeded_upload for u in data["items"])

    def test_search_uploads_by_status(self, client, seeded_upload):
        resp = client.get("/api/uploads/search?status=completed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert all(u["status"] == "completed" for u in data["items"])

    def test_search_uploads_paginated(self, client, seeded_upload):
        resp = client.get("/api/uploads/search?page=1&per_page=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["per_page"] == 10
        assert "items" in data

    def test_search_uploads_from_date(self, client, seeded_upload):
        resp = client.get("/api/uploads/search?from_date=2000-01-01")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_search_uploads_to_date(self, client, seeded_upload):
        resp = client.get("/api/uploads/search?to_date=2099-12-31")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_search_uploads_no_results(self, client):
        resp = client.get("/api/uploads/search?upload_id=NONEXISTENT")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
