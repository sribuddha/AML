"""Add upload_chunk, failed_db_count columns for chunk tracking.

Revision ID: 002_chunk_tracking
Revises: 001_initial
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_chunk_tracking"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("uploaded_files", sa.Column("upload_chunk", sa.Integer(), nullable=True))
    op.add_column("uploaded_files", sa.Column("failed_db_count", sa.Integer(), server_default="0"))


def downgrade() -> None:
    op.drop_column("uploaded_files", "failed_db_count")
    op.drop_column("uploaded_files", "upload_chunk")
