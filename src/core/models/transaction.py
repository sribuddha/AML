import uuid

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.base import Base


class Transaction(Base):
    __tablename__ = "transaction"
    __table_args__ = (
        UniqueConstraint("upload_id", "source_txn_id", name="uq_transaction_upload_source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    upload_id: Mapped[str] = mapped_column(String(36), ForeignKey("uploaded_files.id"), nullable=False)
    account_id: Mapped[str] = mapped_column(String, nullable=False)
    customer_id: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float | None] = mapped_column(Float)
    counterparty: Mapped[str | None] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String)
    state: Mapped[str | None] = mapped_column(String)
    country: Mapped[str | None] = mapped_column(String)
    date: Mapped[str | None] = mapped_column(String)
    source_txn_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="loaded")
    created_at: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[str | None] = mapped_column(String)
