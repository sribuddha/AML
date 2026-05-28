import asyncio
from datetime import datetime, UTC, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.validation_result import ValidationResult
from src.bff.database import get_db
from src.core.models.uploaded_files import UploadedFiles
from src.aml_workflow.services import _set_upload_status

router = APIRouter()


@router.post("/api/uploads/{upload_id}/reprocess", status_code=202)
async def reprocess_upload(upload_id: str, db: AsyncSession = Depends(get_db)):
    upload = await db.get(UploadedFiles, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    status = upload.status

    if status == "complete":
        raise HTTPException(status_code=400, detail="Workflow already complete")

    if status == "pending_human":
        raise HTTPException(status_code=400, detail="Human review in progress")

    if status in ("processing", "uploaded"):
        heartbeat = await db.execute(
            select(func.max(ValidationResult.updated_at))
            .where(
                ValidationResult.upload_id == upload_id,
                ValidationResult.status.in_(["clean", "flagged"]),
            )
        )
        last_heartbeat = heartbeat.scalar()
        if last_heartbeat:
            try:
                last_time = datetime.fromisoformat(last_heartbeat)
                if datetime.now(UTC) - last_time < timedelta(minutes=10):
                    return {"message": "Workflow already in progress"}
            except (ValueError, TypeError):
                pass

        await _set_upload_status(db, upload_id, "uploaded")
        await db.commit()
        return await _start_reprocess(upload_id)

    raise HTTPException(status_code=400, detail=f"Unknown status: {status}")


async def _start_reprocess(upload_id: str):
    async def _run():
        from src.bff.database import async_session_factory
        async with async_session_factory() as workflow_db:
            from src.aml_workflow.triggers import run_validation
            await run_validation(upload_id, workflow_db)

    asyncio.create_task(_run())
    return {"message": "Reprocessing started"}
