from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.models.validation_result import ValidationResult
from src.bff.database import get_db
from src.bff.schemas import (
    PaginatedResponse,
    ValidationByTransactionResponse,
    ValidationDayItem,
    ValidationDetailItem,
    ValidationSummaryResponse,
)
from src.file_processor.models import Transaction, UploadedFiles

router = APIRouter()


@router.get("/api/validation/date/{date}")
async def get_validation_by_date(date: str, db: AsyncSession = Depends(get_db)):
    results = await db.execute(
        select(
            ValidationResult.upload_id,
            func.count().filter(ValidationResult.status == "clean").label("clean_count"),
            func.count().filter(ValidationResult.status == "flagged").label("flagged_count"),
        )
        .where(ValidationResult.validated_at.like(f"{date}%"))
        .group_by(ValidationResult.upload_id)
    )
    items = [
        ValidationDayItem(
            upload_id=row[0],
            clean_count=row[1],
            flagged_count=row[2],
            total_count=row[1] + row[2],
        )
        for row in results.fetchall()
    ]
    return items


@router.get("/api/uploads/{upload_id}/validation")
async def get_validation(
    upload_id: str,
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    upload = await db.get(UploadedFiles, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    if status is None:
        result = await db.execute(
            select(
                func.count().filter(ValidationResult.status == "clean").label("clean_count"),
                func.count().filter(ValidationResult.status == "flagged").label("flagged_count"),
            )
            .where(ValidationResult.upload_id == upload_id)
        )
        row = result.one()
        clean = row[0]
        flagged = row[1]
        return ValidationSummaryResponse(
            upload_id=upload_id,
            clean_count=clean,
            flagged_count=flagged,
            total_count=clean + flagged,
        )

    stmt = (
        select(ValidationResult, Transaction.source_txn_id)
        .join(Transaction, ValidationResult.transaction_id == Transaction.id)
        .where(
            ValidationResult.upload_id == upload_id,
            ValidationResult.status == status,
        )
        .order_by(Transaction.source_txn_id)
    )
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    offset = (page - 1) * per_page
    rows = (await db.execute(stmt.offset(offset).limit(per_page))).all()
    items = [
        ValidationDetailItem(
            source_txn_id=source_txn_id,
            status=vr.status,
            flag_details=vr.flag_details,
        )
        for vr, source_txn_id in rows
    ]
    return PaginatedResponse(page=page, per_page=per_page, total=total, items=items)


@router.get("/api/validation/transaction/{source_txn_id}")
async def get_validation_by_transaction(
    source_txn_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ValidationResult)
        .join(Transaction, ValidationResult.transaction_id == Transaction.id)
        .where(Transaction.source_txn_id == source_txn_id)
        .order_by(ValidationResult.validated_at.desc())
        .limit(1)
    )
    vr = result.scalar_one_or_none()
    if vr is None:
        raise HTTPException(status_code=404, detail="Validation result not found")
    return ValidationByTransactionResponse(
        upload_id=vr.upload_id,
        status=vr.status,
        flag_details=vr.flag_details,
        validated_at=vr.validated_at,
    )
