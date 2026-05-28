import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.types import JSON as JSONType
from sqlalchemy.orm import Mapped, mapped_column

from src.core.base import Base


class ValidationResult(Base):
    __tablename__ = "validation_result"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    upload_id: Mapped[str] = mapped_column(String(36), ForeignKey("uploaded_files.id"), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transaction.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    flag_details: Mapped[dict | None] = mapped_column("details", JSONType, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    triage_reasoning: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_llm_response: Mapped[str | None] = mapped_column(String, nullable=True)
    validated_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[str | None] = mapped_column(String)
