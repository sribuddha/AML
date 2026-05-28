from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bff.database import get_db
from src.core.models.account import Account
from src.core.schemas import PaginatedResponse, TransactionRowResponse
from src.core.models.transaction import Transaction

router = APIRouter()


@router.get("/api/transactions")
async def search_transactions(
    source_txn_id: str | None = Query(None),
    account_id: str | None = Query(None),
    customer_id: str | None = Query(None),
    amount_min: float | None = Query(None),
    amount_max: float | None = Query(None),
    counterparty: str | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TransactionRowResponse]:
    base = select(Transaction).join(Account, Transaction.account_id == Account.account_id)

    if source_txn_id is not None:
        base = base.where(Transaction.source_txn_id == source_txn_id)
    if account_id is not None:
        base = base.where(Transaction.account_id == account_id)
    if customer_id is not None:
        base = base.where(Account.customer_id == customer_id)
    if amount_min is not None:
        base = base.where(Transaction.amount >= amount_min)
    if amount_max is not None:
        base = base.where(Transaction.amount <= amount_max)
    if counterparty is not None:
        base = base.where(Transaction.counterparty.like(f"%{counterparty}%"))
    if from_date is not None:
        base = base.where(Transaction.date >= from_date)
    if to_date is not None:
        base = base.where(Transaction.date <= to_date)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar()

    stmt = (
        base
        .add_columns(Account.name.label("account_name"), Account.customer_id.label("acc_customer_id"))
        .order_by(Transaction.date.desc().nullslast())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    rows = (await db.execute(stmt)).all()

    items = [
        TransactionRowResponse(
            id=txn.id,
            source_txn_id=txn.source_txn_id,
            account_id=txn.account_id,
            account_name=account_name,
            customer_id=acc_customer_id or txn.customer_id,
            amount=txn.amount,
            counterparty=txn.counterparty,
            city=txn.city,
            state=txn.state,
            country=txn.country,
            date=txn.date,
        )
        for txn, account_name, acc_customer_id in rows
    ]

    return PaginatedResponse(page=page, per_page=per_page, total=total, items=items)
