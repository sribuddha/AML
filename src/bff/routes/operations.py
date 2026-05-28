from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.sar import SAR
from src.bff.database import get_db
from src.core.schemas import PaginatedResponse, UploadSummaryResponse
from src.core.models.uploaded_files import UploadedFiles

router = APIRouter()


@router.get("/api/uploads/search")
async def search_uploads(
    upload_id: str | None = Query(None),
    status: str | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[UploadSummaryResponse]:
    stmt = select(UploadedFiles)

    if upload_id is not None:
        stmt = stmt.where(UploadedFiles.id.like(f"%{upload_id}%"))
    if status is not None:
        stmt = stmt.where(UploadedFiles.status == status)
    if from_date is not None:
        stmt = stmt.where(UploadedFiles.uploaded_at >= from_date)
    if to_date is not None:
        stmt = stmt.where(UploadedFiles.uploaded_at <= to_date)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar()

    rows = (
        (await db.execute(
            stmt.order_by(UploadedFiles.uploaded_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        ))
        .scalars()
        .all()
    )

    upload_ids = [u.id for u in rows]
    pending_map: dict[str, int] = {}
    if upload_ids:
        pending_rows = await db.execute(
            select(SAR.upload_id, func.count().label("cnt"))
            .where(SAR.upload_id.in_(upload_ids), SAR.status == "pending_review")
            .group_by(SAR.upload_id)
        )
        for pr in pending_rows:
            pending_map[pr.upload_id] = pr.cnt

    items = [
        UploadSummaryResponse(
            id=u.id,
            filename=u.filename,
            status=u.status,
            total_rows=u.total_rows,
            accepted_count=u.accepted_count,
            failed_count=u.failed_count,
            uploaded_at=u.uploaded_at,
            eval_file=u.eval_file,
            pending_sar_count=pending_map.get(u.id, 0),
        )
        for u in rows
    ]

    return PaginatedResponse(page=page, per_page=per_page, total=total, items=items)
