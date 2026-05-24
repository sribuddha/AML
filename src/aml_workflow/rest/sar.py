import logging
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger("aml_workflow")
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.models.sar import SAR
from src.aml_workflow.models.transaction_status import TransactionStatus
from src.aml_workflow.models.upload_status import UploadStatus
from src.bff.config import DATA_DIR
from src.bff.database import get_db
from src.bff.schemas import PaginatedResponse, ReviewRequest, SARResponse
from src.file_processor.models import UploadedFiles

router = APIRouter()


def _sar_to_response(s: SAR) -> SARResponse:
    return SARResponse(
        id=s.id,
        transaction_id=s.transaction_id,
        upload_id=s.upload_id,
        rule_id=s.rule_id,
        content=s.content,
        status=s.status,
        created_at=s.created_at,
        updated_at=s.updated_at,
        reviewed_at=s.reviewed_at,
        review_notes=s.review_notes,
    )


@router.get("/api/sar/{sar_id}")
async def get_sar(sar_id: str, db: AsyncSession = Depends(get_db)):
    sar = await db.get(SAR, sar_id)
    if sar is None:
        raise HTTPException(status_code=404, detail="SAR not found")
    return _sar_to_response(sar)


@router.patch("/api/sar/{sar_id}/review")
async def review_sar(sar_id: str, body: ReviewRequest, db: AsyncSession = Depends(get_db)):
    sar = await db.get(SAR, sar_id)
    if sar is None:
        raise HTTPException(status_code=404, detail="SAR not found")

    if sar.status != "pending_review":
        raise HTTPException(status_code=400, detail=f"SAR already {sar.status}")

    now = datetime.now(UTC).isoformat()
    previous_status = sar.status
    sar.status = body.action
    sar.reviewed_at = now
    sar.review_notes = body.notes or ""
    sar.updated_at = now

    txn_status = "clean" if body.action == "confirmed" else "dismissed"
    db.add(TransactionStatus(
        transaction_id=sar.transaction_id,
        status=txn_status,
        actor="human",
        created_at=now,
    ))

    await db.commit()

    remaining = await db.execute(
        select(func.count())
        .select_from(SAR)
        .where(SAR.upload_id == sar.upload_id, SAR.status == "pending_review")
    )
    if remaining.scalar() == 0:
        upload = await db.get(UploadedFiles, sar.upload_id)
        if upload and upload.status != "complete":
            upload.status = "complete"
            upload.updated_at = now
            db.add(UploadStatus(
                upload_id=sar.upload_id,
                status="complete",
                actor="system",
                created_at=now,
            ))
            await db.commit()
            logger.info("Upload %s completed after all SARs reviewed", sar.upload_id)

    await db.refresh(sar)
    return _sar_to_response(sar)


@router.get("/api/sar")
async def list_sars(
    upload_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SAR)
    if upload_id:
        stmt = stmt.where(SAR.upload_id == upload_id)
    if status:
        stmt = stmt.where(SAR.status == status)
    stmt = stmt.order_by(SAR.created_at.desc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * per_page
    rows = (await db.execute(stmt.offset(offset).limit(per_page))).scalars().all()

    items = [_sar_to_response(s) for s in rows]
    return PaginatedResponse(page=page, per_page=per_page, total=total, items=items)
