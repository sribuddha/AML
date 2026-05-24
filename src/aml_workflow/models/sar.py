import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.bff.database import Base


class SAR(Base):
    __tablename__ = "sar"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transaction.id"), nullable=False)
    upload_id: Mapped[str] = mapped_column(String(36), ForeignKey("uploaded_files.id"), nullable=False)
    rule_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("rule.id"), nullable=True)
    content: Mapped[str] = mapped_column(String, nullable=False)
    raw_llm_response: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending_review")
    created_at: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[str | None] = mapped_column(String)
    reviewed_at: Mapped[str | None] = mapped_column(String)
    review_notes: Mapped[str | None] = mapped_column(String)
