import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.base import Base


class Rule(Base):
    __tablename__ = "rule"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    type: Mapped[str] = mapped_column(String, nullable=False, server_default="deterministic")
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active")
    rules_json: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[str | None] = mapped_column(String)
