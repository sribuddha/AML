import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.base import Base


class TransactionStatus(Base):
    __tablename__ = "transaction_status"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transaction.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False, server_default="system")
    created_at: Mapped[str] = mapped_column(String, nullable=False)


Index("idx_transaction_status_tx", TransactionStatus.transaction_id, TransactionStatus.created_at)
