import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.bff.database import Base


class Account(Base):
    __tablename__ = "account"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str | None] = mapped_column(String)
    bank: Mapped[str | None] = mapped_column(String)
    date_opened: Mapped[str | None] = mapped_column(String)
    type: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[str | None] = mapped_column(String)
