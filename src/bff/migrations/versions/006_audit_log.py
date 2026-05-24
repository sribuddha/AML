"""Add audit_log table for per-transaction change tracking.

Revision ID: 006_audit_log
Revises: 005_ground_truth
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_audit_log"
down_revision: Union[str, None] = "005_ground_truth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("upload_id", sa.String(36), sa.ForeignKey("uploaded_files.id"), nullable=False),
        sa.Column("transaction_id", sa.String(36), sa.ForeignKey("transaction.id"), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("old_values", sa.String(), nullable=True),
        sa.Column("new_values", sa.String(), nullable=False),
        sa.Column("changed_by", sa.String(), nullable=False, server_default="system"),
        sa.Column("created_at", sa.String(), nullable=True),
    )
    op.create_index("idx_audit_log_upload", "audit_log", ["upload_id"])


def downgrade() -> None:
    op.drop_index("idx_audit_log_upload", table_name="audit_log")
    op.drop_table("audit_log")
