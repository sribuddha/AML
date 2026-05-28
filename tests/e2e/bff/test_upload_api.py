import uuid
import pandas as pd
from datetime import datetime, UTC
from pathlib import Path

import pytest
import pytest_asyncio

from src.bff.config import get_upload_dir
from src.core.models.uploaded_files import UploadedFiles


@pytest_asyncio.fixture
async def seeded_retry_upload(seeded_session):
    now = datetime.now(UTC).isoformat()
    upload_id = str(uuid.uuid4())
    upload = UploadedFiles(
        id=upload_id, filename="retry_test.csv", status="failed",
        total_rows=1, accepted_count=0, failed_count=1,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    await seeded_session.commit()

    staging_dir = get_upload_dir() / "staging" / upload_id
    staging_dir.mkdir(parents=True, exist_ok=True)

    val_df = pd.DataFrame([{
        "account_id": "ACC001", "customer_id": "CUST001",
        "amount": 100.0, "counterparty": "Test Corp",
        "location": "New York", "date": "2026-01-15",
        "source_txn_id": f"RTYTXN{uuid.uuid4().hex[:4]}",
    }])
    val_df.to_csv(staging_dir / "0.val", index=False)

    return upload_id


class TestUploadAPI:
    async def test_upload_valid_csv(self, client, sample_csv_path):
        csv_bytes = sample_csv_path.read_bytes()
        resp = await client.post("/api/uploads", files={"file": ("test.csv", csv_bytes, "text/csv")})
        assert resp.status_code == 200
        data = resp.json()
        assert "upload_id" in data
        assert data["status"] == "completed"

    async def test_upload_non_csv_returns_400(self, client):
        resp = await client.post("/api/uploads", files={"file": ("test.txt", b"hello world", "text/plain")})
        assert resp.status_code == 400
        assert "CSV" in resp.json()["detail"]

    async def test_upload_malformed_csv_returns_400(self, client):
        resp = await client.post("/api/uploads", files={"file": ("bad.csv", b"\xff\xfe\x00\x01", "text/csv")})
        assert resp.status_code == 400
        assert "Could not parse CSV" in resp.json()["detail"]

    async def test_upload_missing_columns_returns_400(self, client):
        csv_bytes = b"col1,col2\n1,2\n3,4"
        resp = await client.post("/api/uploads", files={"file": ("bad.csv", csv_bytes, "text/csv")})
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "Missing required columns" in detail

    async def test_retry_with_valid_upload(self, client, seeded_retry_upload):
        upload_id = seeded_retry_upload
        resp = await client.post(f"/api/uploads/{upload_id}/retry")
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "completed"

    async def test_retry_with_invalid_upload_returns_404(self, client):
        resp = await client.post(f"/api/uploads/{uuid.uuid4()}/retry")
        assert resp.status_code == 404
