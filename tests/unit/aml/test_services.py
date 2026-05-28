import uuid
from datetime import datetime, UTC

import pytest

from src.aml_workflow.services import (
    _set_upload_status,
    record_transaction_status,
)
from src.core.models.uploaded_files import UploadedFiles
from src.aml_workflow.models.transaction_status import TransactionStatus


class TestSetUploadStatus:
    async def test_upload_not_found(self, seeded_session):
        uid = str(uuid.uuid4())
        await _set_upload_status(seeded_session, uid, "processing")
        statuses = (await seeded_session.execute(
            __import__("sqlalchemy").select(UploadedFiles).where(UploadedFiles.id == uid)
        )).scalars().all()
        assert len(statuses) == 0

    async def test_upload_found(self, seeded_session):
        uid = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        upload = UploadedFiles(
            id=uid, filename="t.csv", status="uploaded",
            uploaded_at=now, created_at=now, updated_at=now,
        )
        seeded_session.add(upload)
        await _set_upload_status(seeded_session, uid, "processing")
        assert upload.status == "processing"


class TestRecordTransactionStatus:
    async def test_records_status(self, seeded_session):
        txn_id = str(uuid.uuid4())
        await record_transaction_status(seeded_session, txn_id, "clean")
        rows = (await seeded_session.execute(
            __import__("sqlalchemy").select(TransactionStatus).where(
                TransactionStatus.transaction_id == txn_id
            )
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "clean"
