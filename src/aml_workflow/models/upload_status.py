import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.bff.database import Base


class UploadStatus(Base):
    __tablename__ = "upload_status"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    upload_id: Mapped[str] = mapped_column(String(36), ForeignKey("uploaded_files.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False, server_default="system")
    created_at: Mapped[str] = mapped_column(String, nullable=False)


Index("idx_upload_status_upload", UploadStatus.upload_id, UploadStatus.created_at)
