import uuid
from datetime import datetime, UTC

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.bff.database import get_db
from src.bff.app import app
from src.file_processor.models import UploadedFiles, Transaction
from src.file_processor.service import process_upload
from tests.helpers import upload_csv


@pytest.fixture
def client(seeded_session):
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_reprocess_upload(seeded_session, client, sample_csv_path):
    upload_id = await upload_csv(seeded_session, sample_csv_path)

    resp = client.post(f"/api/uploads/{upload_id}/reprocess")
    assert resp.status_code == 202
    data = resp.json()
    assert "message" in data


@pytest.mark.asyncio
async def test_reprocess_returns_200_for_valid_upload(seeded_session, client, sample_csv_path):
    upload_id = await upload_csv(seeded_session, sample_csv_path)

    resp = client.post(f"/api/uploads/{upload_id}/reprocess")
    assert resp.status_code == 202
