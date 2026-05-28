from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bff.database import get_db
from src.core.models.account import Account
from src.core.models.customer import Customer
from src.core.schemas import (
    AccountDetailResponse,
    CustomerDetailResponse,
    CustomerSummaryResponse,
    PaginatedResponse,
)

router = APIRouter()


@router.get("/api/customers")
async def list_customers(
    first_name: str | None = Query(None),
    last_name: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[CustomerSummaryResponse]:
    stmt = select(Customer)

    if first_name is not None:
        stmt = stmt.where(Customer.first_name.like(f"%{first_name}%"))
    if last_name is not None:
        stmt = stmt.where(Customer.last_name.like(f"%{last_name}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar()

    rows = (
        (await db.execute(
            stmt.order_by(Customer.last_name, Customer.first_name)
            .offset((page - 1) * per_page)
            .limit(per_page)
        ))
        .scalars()
        .all()
    )

    items = [
        CustomerSummaryResponse(
            customer_id=c.customer_id,
            first_name=c.first_name,
            last_name=c.last_name,
            city=c.city,
            state=c.state,
        )
        for c in rows
    ]

    return PaginatedResponse(page=page, per_page=per_page, total=total, items=items)


@router.get("/api/customers/{customer_id}")
async def get_customer(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
) -> CustomerDetailResponse:
    customer = (
        await db.execute(select(Customer).where(Customer.customer_id == customer_id))
    ).scalar()

    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    accounts = (
        (await db.execute(
            select(Account).where(Account.customer_id == customer_id)
        ))
        .scalars()
        .all()
    )

    return CustomerDetailResponse(
        customer_id=customer.customer_id,
        first_name=customer.first_name,
        last_name=customer.last_name,
        address_line=customer.address_line,
        city=customer.city,
        state=customer.state,
        zip=customer.zip,
        accounts=[
            AccountDetailResponse(
                account_id=a.account_id,
                name=a.name,
                bank=a.bank,
                type=a.type,
                date_opened=a.date_opened,
            )
            for a in accounts
        ],
    )
