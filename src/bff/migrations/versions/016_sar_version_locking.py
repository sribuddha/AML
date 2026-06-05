"""add version column to sar for optimistic locking

Revision ID: 016_sar_version_locking
Revises: 1aa1b8a8d95c
Create Date: 2026-06-05 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "016_sar_version_locking"
down_revision: Union[str, None] = "1aa1b8a8d95c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sar", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("sar", "version")
