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

    @patch("pandas.read_csv", side_effect=pd.errors.ParserError("mock error"))
    def test_upload_invalid_csv(self, mock_read, client):
        resp = client.post("/api/uploads", files={"file": ("bad.csv", b"x", "text/csv")})
        assert resp.status_code == 400
        assert "Could not parse CSV" in resp.json()["detail"]

    def test_upload_missing_columns(self, client):
        content = _build_csv([{"foo": "1", "bar": "2"}])
        resp = client.post("/api/uploads", files={"file": ("test.csv", content, "text/csv")})
        assert resp.status_code == 400
        assert "Missing required columns" in resp.json()["detail"]

    @patch("pandas.read_csv", side_effect=pd.errors.ParserError("mock error"))
    @patch("src.file_processor.rest.upload.process_upload")
    @patch("src.file_processor.rest.upload.asyncio.create_task")
    def test_upload_from_work_invalid_csv(self, mock_task, mock_process, mock_read, client, seeded_session):
        mock_process.return_value = {"upload_id": str(uuid.uuid4()), "accepted": 0, "rejected": 0}
        file_path = WORK_DIR / "bad_work.csv"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"x")
        resp = client.post("/api/uploads/from-work/bad_work.csv")
        assert resp.status_code == 400
        assert "Could not parse CSV" in resp.json()["detail"]

    @patch("src.file_processor.rest.upload.process_upload")
    @patch("src.file_processor.rest.upload.asyncio.create_task")
    def test_upload_from_work_missing_columns(self, mock_task, mock_process, client, seeded_session):
        mock_process.return_value = {"upload_id": str(uuid.uuid4()), "accepted": 0, "rejected": 0}
        csv_content = _build_csv([{"foo": "1", "bar": "2"}])
        file_path = WORK_DIR / "bad_cols.csv"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(csv_content)
        resp = client.post("/api/uploads/from-work/bad_cols.csv")
        assert resp.status_code == 400
        assert "Missing required columns" in resp.json()["detail"]

    @patch("src.file_processor.rest.upload.process_upload")
    @patch("src.file_processor.rest.upload.asyncio.create_task")
    def test_upload_from_work_with_source_txn_and_eval(self, mock_task, mock_process, client, seeded_session):
        mock_process.return_value = {"upload_id": str(uuid.uuid4()), "accepted": 1, "rejected": 0}
        csv_content = _build_csv([
            {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100,
             "counterparty": "Test", "location": "New York", "date": "2026-05-01",
             "source_txn_id": "TXN001"},
        ])
        file_path = WORK_DIR / "with_eval.csv"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(csv_content)
        eval_path = file_path.with_suffix(".eval")
        eval_path.write_text("[]")

        resp = client.post("/api/uploads/from-work/with_eval.csv")
        assert resp.status_code == 200

    @patch("src.file_processor.rest.upload.process_upload")
    @patch("src.file_processor.rest.upload.asyncio.create_task")
    def test_upload_from_work_with_manifest(self, mock_task, mock_process, client, seeded_session):
        mock_process.return_value = {"upload_id": str(uuid.uuid4()), "accepted": 1, "rejected": 0}
        csv_content = _build_csv([
            {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100,
             "counterparty": "Test", "location": "New York", "date": "2026-05-01"},
        ])
        file_path = WORK_DIR / "with_manifest.csv"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(csv_content)
        manifest_path = file_path.with_suffix(".manifest.json")
        manifest_path.write_text('{"version": 1, "entries": []}')

        resp = client.post("/api/uploads/from-work/with_manifest.csv")
        assert resp.status_code == 200

    @patch("src.file_processor.rest.upload.process_upload")
    @patch("src.file_processor.rest.upload.asyncio.create_task")
    def test_upload_from_work_empty_manifest_falls_back_to_eval(self, mock_task, mock_process, client, seeded_session):
        mock_process.return_value = {"upload_id": str(uuid.uuid4()), "accepted": 1, "rejected": 0}
        csv_content = _build_csv([
            {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100,
             "counterparty": "Test", "location": "New York", "date": "2026-05-01"},
        ])
        file_path = WORK_DIR / "empty_manifest.csv"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(csv_content)
        manifest_path = file_path.with_suffix(".manifest.json")
        manifest_path.write_text("[]")
        eval_path = file_path.with_suffix(".eval")
        eval_path.write_text('["fallback"]')

        resp = client.post("/api/uploads/from-work/empty_manifest.csv")
        assert resp.status_code == 200

    @patch("src.file_processor.rest.upload.process_upload")
    @patch("src.file_processor.rest.upload.asyncio.create_task")
    def test_upload_from_work_bad_manifest_falls_back(self, mock_task, mock_process, client, seeded_session):
        mock_process.return_value = {"upload_id": str(uuid.uuid4()), "accepted": 1, "rejected": 0}
        csv_content = _build_csv([
            {"account_id": "ACC001", "customer_id": "CUST001", "amount": 100,
             "counterparty": "Test", "location": "New York", "date": "2026-05-01"},
        ])
        file_path = WORK_DIR / "bad_manifest.csv"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(csv_content)
        manifest_path = file_path.with_suffix(".manifest.json")
        manifest_path.write_text("not valid json")
        eval_path = file_path.with_suffix(".eval")
        eval_path.write_text('["fallback"]')

        resp = client.post("/api/uploads/from-work/bad_manifest.csv")
        assert resp.status_code == 200
