import uuid
from datetime import datetime, UTC

import pytest
import pytest_asyncio

from src.aml_workflow.models.validation_result import ValidationResult
from src.aml_workflow.models.upload_status import UploadStatus
from src.file_processor.models import UploadedFiles, Transaction


@pytest_asyncio.fixture
async def seeded_complete_upload(seeded_session):
    now = datetime.now(UTC).isoformat()
    uid = str(uuid.uuid4())
    upload = UploadedFiles(
        id=uid, filename="complete.csv", status="complete",
        total_rows=5, accepted_count=5, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    await seeded_session.commit()
    return uid


@pytest_asyncio.fixture
async def seeded_pending_human_upload(seeded_session):
    now = datetime.now(UTC).isoformat()
    uid = str(uuid.uuid4())
    upload = UploadedFiles(
        id=uid, filename="pending.csv", status="pending_human",
        total_rows=5, accepted_count=5, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)
    await seeded_session.commit()
    return uid


@pytest_asyncio.fixture
async def seeded_processing_upload_with_heartbeat(seeded_session):
    now = datetime.now(UTC).isoformat()
    uid = str(uuid.uuid4())
    upload = UploadedFiles(
        id=uid, filename="processing.csv", status="processing",
        total_rows=5, accepted_count=5, failed_count=0,
        uploaded_at=now, created_at=now, updated_at=now,
    )
    seeded_session.add(upload)

    txn = Transaction(
        id=str(uuid.uuid4()), upload_id=uid,
        account_id="ACC001", customer_id="CUST001",
        amount=100.0, counterparty="Test",
        city="NYC", state="NY", country="US",
        date="2026-05-01", source_txn_id="PROCTXN",
        created_at=now, updated_at=now,
    )
    seeded_session.add(txn)

    vr = ValidationResult(
        id=str(uuid.uuid4()), upload_id=uid,
        transaction_id=txn.id, status="clean",
        flag_details=None, validated_at=now,
        created_at=now, updated_at=now,
    )
    seeded_session.add(vr)
    await seeded_session.commit()
    return uid


class TestReprocessAPI:
    async def test_reprocess_non_existent_upload_returns_404(self, client):
        resp = await client.post(f"/api/uploads/{uuid.uuid4()}/reprocess")
        assert resp.status_code == 404

    async def test_reprocess_complete_upload_returns_400(self, client, seeded_complete_upload):
        resp = await client.post(f"/api/uploads/{seeded_complete_upload}/reprocess")
        assert resp.status_code == 400
        assert "complete" in resp.json()["detail"].lower()

    async def test_reprocess_pending_human_upload_returns_400(self, client, seeded_pending_human_upload):
        resp = await client.post(f"/api/uploads/{seeded_pending_human_upload}/reprocess")
        assert resp.status_code == 400
        assert "human" in resp.json()["detail"].lower()

    async def test_reprocess_processing_within_heartbeat(self, client, seeded_processing_upload_with_heartbeat):
        uid = seeded_processing_upload_with_heartbeat
        resp = await client.post(f"/api/uploads/{uid}/reprocess")
        assert resp.status_code == 202
        data = resp.json()
        assert data["message"] == "Workflow already in progress"
