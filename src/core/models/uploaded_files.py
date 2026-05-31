import uuid

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.base import Base


class UploadedFiles(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename: Mapped[str] = mapped_column(String, nullable=False)
    upload_chunk: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    total_rows: Mapped[int | None] = mapped_column(Integer)
    accepted_count: Mapped[int | None] = mapped_column(Integer)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_db_count: Mapped[int] = mapped_column(Integer, server_default="0")
    uploaded_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[str | None] = mapped_column(String)
    eval_file: Mapped[str | None] = mapped_column(String, nullable=True)
    mode: Mapped[str | None] = mapped_column(String, nullable=True, default="full")
