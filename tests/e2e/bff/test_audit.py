import uuid
from io import BytesIO

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.bff.database import get_db
from src.bff.app import app
from src.file_processor.models import UploadedFiles
from src.file_processor.service import process_upload
from tests.helpers import upload_csv


@pytest.fixture
def client(seeded_session):
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_and_check_status(seeded_session, client, sample_csv_path):
    upload_id = await upload_csv(seeded_session, sample_csv_path)

    resp = client.get(f"/api/uploads/{upload_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_unknown_upload_id_returns_404(client):
    resp = client.get("/api/uploads/nonexistent-id-12345/status")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_multiple_uploads_status(seeded_session, client, sample_csv_path):
    upload_id_1 = await upload_csv(seeded_session, sample_csv_path)
    upload_id_2 = await upload_csv(seeded_session, sample_csv_path)

    resp1 = client.get(f"/api/uploads/{upload_id_1}/status")
    assert resp1.status_code == 200

    resp2 = client.get(f"/api/uploads/{upload_id_2}/status")
    assert resp2.status_code == 200
