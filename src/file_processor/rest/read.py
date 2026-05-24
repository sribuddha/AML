import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bff.database import get_db
from src.bff.schemas import (
    PaginatedResponse,
    RejectedRecordResponse,
    TransactionResponse,
    UploadSummaryResponse,
)
from src.file_processor.models import RejectedRecord, Transaction, UploadedFiles

router = APIRouter()


async def _paginate(db: AsyncSession, stmt, page: int, per_page: int):
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    offset = (page - 1) * per_page
    rows = (await db.execute(stmt.offset(offset).limit(per_page))).scalars().all()
    return total, rows


# ─── Uploads ────────────────────────────────────────────────────────────────


@router.get("/api/uploads")
async def list_uploads(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(UploadedFiles).order_by(UploadedFiles.uploaded_at.desc().nullslast())
    total, rows = await _paginate(db, stmt, page, per_page)
    items = [
        UploadSummaryResponse(
            id=r.id,
            filename=r.filename,
            status=r.status,
            total_rows=r.total_rows,
            accepted_count=r.accepted_count,
            failed_count=r.failed_count,
            uploaded_at=r.uploaded_at,
        )
        for r in rows
    ]
    return PaginatedResponse(page=page, per_page=per_page, total=total, items=items)


@router.get("/api/uploads/{upload_id}")
async def get_upload(upload_id: str, db: AsyncSession = Depends(get_db)):
    r = await db.get(UploadedFiles, upload_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return UploadSummaryResponse(
        id=r.id,
        filename=r.filename,
        status=r.status,
        total_rows=r.total_rows,
        accepted_count=r.accepted_count,
        failed_count=r.failed_count,
        uploaded_at=r.uploaded_at,
    )


# ─── Transactions ───────────────────────────────────────────────────────────


@router.get("/api/uploads/{upload_id}/transactions")
async def list_transactions(
    upload_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    upload = await db.get(UploadedFiles, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    stmt = (
        select(Transaction)
        .where(Transaction.upload_id == upload_id)
        .order_by(Transaction.source_txn_id)
    )
    total, rows = await _paginate(db, stmt, page, per_page)
    items = [
        TransactionResponse(
            id=r.id,
            account_id=r.account_id,
            customer_id=r.customer_id,
            amount=r.amount,
            counterparty=r.counterparty,
            city=r.city,
            state=r.state,
            country=r.country,
            date=r.date,
        )
        for r in rows
    ]
    return PaginatedResponse(page=page, per_page=per_page, total=total, items=items)


@router.get("/api/transactions/{transaction_id}")
async def get_transaction(transaction_id: str, db: AsyncSession = Depends(get_db)):
    t = await db.get(Transaction, transaction_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return TransactionResponse(
        id=t.id,
        account_id=t.account_id,
        customer_id=t.customer_id,
        amount=t.amount,
        counterparty=t.counterparty,
        city=t.city,
        state=t.state,
        country=t.country,
        date=t.date,
    )


# ─── Rejected Records ──────────────────────────────────────────────────────


@router.get("/api/uploads/{upload_id}/rejected")
async def list_rejected_records(
    upload_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    upload = await db.get(UploadedFiles, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    stmt = (
        select(RejectedRecord)
        .where(RejectedRecord.upload_id == upload_id)
        .order_by(RejectedRecord.row_index)
    )
    total, rows = await _paginate(db, stmt, page, per_page)
    items = []
    for r in rows:
        raw_data = {}
        if r.raw_data:
            try:
                raw_data = json.loads(r.raw_data)
            except (json.JSONDecodeError, TypeError):
                raw_data = {"raw": r.raw_data}
        reasons_list = []
        if r.reasons:
            try:
                reasons_list = json.loads(r.reasons)
            except (json.JSONDecodeError, TypeError):
                reasons_list = [r.reasons]
        items.append(RejectedRecordResponse(
            id=r.id,
            row_index=r.row_index,
            raw_data=raw_data,
            reasons=reasons_list,
        ))
    return PaginatedResponse(page=page, per_page=per_page, total=total, items=items)
