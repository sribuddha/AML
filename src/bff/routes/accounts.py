from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bff.database import get_db
from src.bff.models.account import Account
from src.bff.schemas import AccountResponse

router = APIRouter()


@router.get("/api/accounts/{account_id}")
async def get_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    account = (
        await db.execute(select(Account).where(Account.account_id == account_id))
    ).scalar()

    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    return AccountResponse(
        account_id=account.account_id,
        name=account.name,
        bank=account.bank,
        type=account.type,
        date_opened=account.date_opened,
        customer_id=account.customer_id,
    )
