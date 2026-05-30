from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.bff.logger import logger
from src.core.utils import now


async def _set_upload_status(db: AsyncSession, upload_id: str, status: str) -> None:
    """Update upload entity status and append status log entry. Does NOT commit."""
    from src.core.models.uploaded_files import UploadedFiles
    from src.aml_workflow.models.upload_status import UploadStatus

    upload = await db.get(UploadedFiles, upload_id)
    if upload:
        upload.status = status
        upload.updated_at = now()
    else:
        logger.warning("Upload %s not found — status log only", upload_id)

    db.add(UploadStatus(
        upload_id=upload_id,
        status=status,
        actor="system",
        created_at=now(),
    ))


async def transition_upload(db: AsyncSession, upload_id: str, status: str) -> None:
    """Update upload status and commit immediately."""
    await _set_upload_status(db, upload_id, status)
    await db.commit()
    logger.info("Upload %s → %s", upload_id, status)


async def record_transaction_status(db: AsyncSession, transaction_id: str, status: str, actor: str = "system") -> None:
    """Append a TransactionStatus log entry. Does NOT commit."""
    from src.aml_workflow.models.transaction_status import TransactionStatus

    db.add(TransactionStatus(
        transaction_id=transaction_id,
        status=status,
        actor=actor,
        created_at=now(),
    ))


async def trigger_workflow(upload_id: str) -> None:
    """Run the AML workflow for an upload in a fresh DB session. Logs but does not propagate errors."""
    try:
        from src.bff.database import async_session_factory
        async with async_session_factory() as workflow_db:
            from src.aml_workflow.triggers import run_validation
            await run_validation(upload_id, workflow_db)
    except Exception:
        logger.exception("Background workflow failed for upload %s", upload_id)
