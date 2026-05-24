"""Add review_status, triage columns, and sar table for Phase 6.

Revision ID: 004_phase6
Revises: 003_rule_type
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_phase6"
down_revision: Union[str, None] = "003_rule_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("uploaded_files", sa.Column("review_status", sa.String(), nullable=True))
    op.add_column("validation_result", sa.Column("risk_level", sa.String(), nullable=True))
    op.add_column("validation_result", sa.Column("category", sa.String(), nullable=True))
    op.add_column("validation_result", sa.Column("triage_reasoning", sa.String(), nullable=True))
    op.create_table(
        "sar",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transaction_id", sa.String(36), sa.ForeignKey("transaction.id"), nullable=False),
        sa.Column("upload_id", sa.String(36), sa.ForeignKey("uploaded_files.id"), nullable=False),
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("rule.id"), nullable=True),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending_review"),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.String(), nullable=True),
        sa.Column("review_notes", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("sar")
    op.drop_column("validation_result", "triage_reasoning")
    op.drop_column("validation_result", "category")
    op.drop_column("validation_result", "risk_level")
    op.drop_column("uploaded_files", "review_status")
