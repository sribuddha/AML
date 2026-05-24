"""Add type column to rule table (deterministic / llm).

Revision ID: 003_rule_type
Revises: 002_chunk_tracking
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_rule_type"
down_revision: Union[str, None] = "002_chunk_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rule", sa.Column("type", sa.String(), nullable=False, server_default="deterministic"))


def downgrade() -> None:
    op.drop_column("rule", "type")
