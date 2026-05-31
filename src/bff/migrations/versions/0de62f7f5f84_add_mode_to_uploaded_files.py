"""add_mode_to_uploaded_files

Revision ID: 0de62f7f5f84
Revises: 015_sar_llm_fields
Create Date: 2026-05-31 09:13:05.948379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0de62f7f5f84'
down_revision: Union[str, None] = '015_sar_llm_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("uploaded_files", sa.Column("mode", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("uploaded_files", "mode")
