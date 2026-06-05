import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("aml_workflow")
from src.core.utils import now as _now
from src.core.models.sar import SAR
from src.aml_workflow.models.transaction_status import TransactionStatus
from src.bff.database import get_db
from src.aml_workflow.services import _set_upload_status
from src.core.schemas import BatchReviewRequest, PaginatedResponse, ReviewRequest, SARResponse
from src.core.models.uploaded_files import UploadedFiles

_sar_locks: dict[str, asyncio.Lock] = {}

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


@router.post("/api/sar/batch-review")
async def batch_review_sars(body: BatchReviewRequest, db: AsyncSession = Depends(get_db)):
    if body.action not in ("confirmed", "dismissed"):
        raise HTTPException(status_code=400, detail="Action must be 'confirmed' or 'dismissed'")

    if not body.sar_ids:
        raise HTTPException(status_code=400, detail="sar_ids list is empty")

    now = _now()
    txn_status = "clean" if body.action == "confirmed" else "dismissed"

    reviewed = 0
    conflicts: list[str] = []
    uploads_affected: set[str] = set()

    for sar_id in sorted(body.sar_ids):
        lock = _sar_locks.setdefault(sar_id, asyncio.Lock())
        async with lock:
            sar = await db.get(SAR, sar_id)
            if sar is None or sar.status != "pending_review":
                continue

            expected_version = sar.version
            result = await db.execute(
                sa_update(SAR)
                .where(SAR.id == sar_id, SAR.version == expected_version)
                .values(
                    status=body.action,
                    version=SAR.version + 1,
                    reviewed_at=now,
                    updated_at=now,
                )
            )
            if result.rowcount == 0:
                conflicts.append(sar_id)
                continue

            reviewed += 1
            uploads_affected.add(sar.upload_id)
            db.add(TransactionStatus(
                transaction_id=sar.transaction_id,
                status=txn_status,
                actor="human",
                created_at=now,
            ))

    if not reviewed:
        raise HTTPException(status_code=404, detail="No pending SARs found for the given IDs")

    for uid in uploads_affected:
        remaining = await db.execute(
            select(func.count())
            .select_from(SAR)
            .where(SAR.upload_id == uid, SAR.status == "pending_review")
        )
        if remaining.scalar() == 0:
            upload = await db.get(UploadedFiles, uid)
            if upload and upload.status != "complete":
                await _set_upload_status(db, uid, "complete")

    await db.commit()
    logger.info("Batch %s %d SARs (%d conflicts)", body.action, reviewed, len(conflicts))

    return {"reviewed": reviewed, "action": body.action, "conflicts": conflicts}


@router.get("/api/sar/{sar_id}")
async def get_sar(sar_id: str, db: AsyncSession = Depends(get_db)):
    sar = await db.get(SAR, sar_id)
    if sar is None:
        raise HTTPException(status_code=404, detail="SAR not found")
    return _sar_to_response(sar)


@router.patch("/api/sar/{sar_id}/review")
async def review_sar(sar_id: str, body: ReviewRequest, db: AsyncSession = Depends(get_db)):
    lock = _sar_locks.setdefault(sar_id, asyncio.Lock())
    async with lock:
        sar = await db.get(SAR, sar_id)
        if sar is None:
            raise HTTPException(status_code=404, detail="SAR not found")

        if sar.status != "pending_review":
            raise HTTPException(status_code=400, detail=f"SAR already {sar.status}")

        now = _now()
        upload_id = sar.upload_id
        transaction_id = sar.transaction_id
        expected_version = sar.version

        result = await db.execute(
            sa_update(SAR)
            .where(SAR.id == sar_id, SAR.version == expected_version)
            .values(
                status=body.action,
                version=SAR.version + 1,
                reviewed_at=now,
                review_notes=body.notes or "",
                updated_at=now,
            )
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="SAR was already reviewed by another user")

        txn_status = "clean" if body.action == "confirmed" else "dismissed"
        db.add(TransactionStatus(
            transaction_id=transaction_id,
            status=txn_status,
            actor="human",
            created_at=now,
        ))

        await db.commit()

        remaining = await db.execute(
            select(func.count())
            .select_from(SAR)
            .where(SAR.upload_id == upload_id, SAR.status == "pending_review")
        )
        if remaining.scalar() == 0:
            upload = await db.get(UploadedFiles, upload_id)
            if upload and upload.status != "complete":
                await _set_upload_status(db, upload_id, "complete")
                await db.commit()
                logger.info("Upload %s completed after all SARs reviewed", upload_id)

        updated = await db.get(SAR, sar_id)
        return _sar_to_response(updated)


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
