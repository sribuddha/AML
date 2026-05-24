"""add eval_file column to uploaded_files

Revision ID: 014_eval_file
Revises: 013_location_split
Create Date: 2026-05-24 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "014_eval_file"
down_revision: Union[str, None] = "013_location_split"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("uploaded_files", sa.Column("eval_file", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("uploaded_files", "eval_file")
