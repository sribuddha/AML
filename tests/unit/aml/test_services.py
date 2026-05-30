import uuid
from datetime import datetime, UTC
from unittest.mock import AsyncMock, patch

import pytest

from src.aml_workflow.services import (
    _set_upload_status,
    record_transaction_status,
    trigger_workflow,
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


class TestTriggerWorkflow:
    async def test_calls_run_validation(self):
        import sys
        mock_triggers = type(sys)("src.aml_workflow.triggers")
        mock_triggers.run_validation = AsyncMock()
        sys.modules["src.aml_workflow.triggers"] = mock_triggers

        mock_session = AsyncMock()
        with patch("src.bff.database.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session
            await trigger_workflow("test-upload-id")

        mock_triggers.run_validation.assert_awaited_once_with("test-upload-id", mock_session)

    async def test_logs_error_on_failure(self):
        import sys
        mock_triggers = type(sys)("src.aml_workflow.triggers")
        mock_triggers.run_validation = AsyncMock()
        sys.modules["src.aml_workflow.triggers"] = mock_triggers

        with (
            patch("src.bff.database.async_session_factory") as mock_factory,
            patch("src.aml_workflow.services.logger.exception") as mock_log,
        ):
            mock_factory.return_value.__aenter__.side_effect = RuntimeError("DB down")
            await trigger_workflow("test-upload-id")

        mock_log.assert_called_once()
        args, _ = mock_log.call_args
        assert "Background workflow failed" in args[0]
        assert args[1] == "test-upload-id"

    async def test_does_not_re_raise(self):
        import sys
        mock_triggers = type(sys)("src.aml_workflow.triggers")
        mock_triggers.run_validation = AsyncMock()
        sys.modules["src.aml_workflow.triggers"] = mock_triggers

        with patch("src.bff.database.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.side_effect = RuntimeError("DB down")
            await trigger_workflow("test-upload-id")

    async def test_passes_upload_id_correctly(self):
        import sys
        mock_triggers = type(sys)("src.aml_workflow.triggers")
        mock_triggers.run_validation = AsyncMock()
        sys.modules["src.aml_workflow.triggers"] = mock_triggers

        mock_session = AsyncMock()
        with patch("src.bff.database.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session
            await trigger_workflow("upload-42")

        mock_triggers.run_validation.assert_awaited_once_with("upload-42", mock_session)
