import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.base import Base


class WorkflowJob(Base):
    __tablename__ = "workflow_job"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    upload_id: Mapped[str] = mapped_column(String(36), ForeignKey("uploaded_files.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    mode: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
