import uuid
from io import BytesIO
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.bff.database import get_db
from src.bff.config import BASE_DIR


WORK_DIR = BASE_DIR / "work"


@pytest.fixture
def client(seeded_session):
    app = FastAPI()
    from src.file_processor.rest.upload import router
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c


def _build_csv(rows: list[dict]) -> bytes:
    df = pd.DataFrame(rows)
    buf = BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


class TestUploadRest:
    def test_upload_no_file(self, client):
        resp = client.post("/api/uploads")
        assert resp.status_code == 422

    @patch("src.file_processor.rest.upload.process_upload")
    @patch("src.file_processor.rest.upload.asyncio.create_task")
    def test_upload_valid_csv(self, mock_task, mock_process, client, sample_csv_path):
        mock_process.return_value = {
            "upload_id": str(uuid.uuid4()),
            "accepted": 8,
            "rejected": 2,
        }
        with open(sample_csv_path, "rb") as f:
            resp = client.post("/api/uploads", files={"file": ("test.csv", f, "text/csv")})
        assert resp.status_code == 200
        data = resp.json()
        assert "upload_id" in data
        assert data["accepted"] == 8

    def test_upload_non_csv(self, client):
        resp = client.post("/api/uploads", files={"file": ("test.txt", b"hello", "text/plain")})
        assert resp.status_code == 400
        assert "Only CSV files" in resp.json()["detail"]

    @patch("src.file_processor.rest.upload.process_upload")
    @patch("src.file_processor.rest.upload.asyncio.create_task")
    def test_upload_from_work(self, mock_task, mock_process, client, seeded_session, tmp_path):
        mock_process.return_value = {
            "upload_id": str(uuid.uuid4()),
            "accepted": 5,
            "rejected": 0,
        }
        csv_content = _build_csv([
            {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100, "counterparty": "Test", "location": "New York", "date": "2026-05-01"},
        ])
        file_path = WORK_DIR / "test_work.csv"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(csv_content)

        resp = client.post("/api/uploads/from-work/test_work.csv")
        assert resp.status_code == 200
        data = resp.json()
        assert "upload_id" in data

    def test_upload_from_work_not_found(self, client):
        resp = client.post("/api/uploads/from-work/nonexistent.csv")
        assert resp.status_code == 404

    def test_upload_retry_not_found(self, client):
        resp = client.post("/api/uploads/nonexistent/retry")
        assert resp.status_code == 404

    @patch("src.file_processor.rest.upload.retry_upload")
    def test_upload_retry_success(self, mock_retry, client, seeded_session):
        mock_retry.return_value = {"upload_id": "test-uid", "retried": 5}
        uid = str(uuid.uuid4())
        resp = client.post(f"/api/uploads/{uid}/retry")
        assert resp.status_code == 201
        data = resp.json()
        assert "upload_id" in data
