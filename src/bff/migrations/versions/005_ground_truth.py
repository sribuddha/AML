"""Add ground_truth column to transaction for eval dataset labeling.

Revision ID: 005_ground_truth
Revises: 004_phase6
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_ground_truth"
down_revision: Union[str, None] = "004_phase6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transaction", sa.Column("ground_truth", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("transaction", "ground_truth")
