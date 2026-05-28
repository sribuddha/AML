from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.models.upload_status import UploadStatus
from src.bff.database import get_db
from src.core.models.uploaded_files import UploadedFiles
from src.core.schemas import UploadStatusResponse, PaginatedResponse

router = APIRouter()


@router.get("/api/uploads/{upload_id}/status")
async def list_upload_status(
    upload_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    upload = await db.get(UploadedFiles, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    stmt = (
        select(UploadStatus)
        .where(UploadStatus.upload_id == upload_id)
        .order_by(UploadStatus.created_at.desc())
    )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * per_page
    rows = (await db.execute(stmt.offset(offset).limit(per_page))).scalars().all()

    items = [UploadStatusResponse(
        id=r.id,
        upload_id=r.upload_id,
        status=r.status,
        actor=r.actor,
        created_at=r.created_at,
    ) for r in rows]
    return PaginatedResponse(page=page, per_page=per_page, total=total, items=items)
