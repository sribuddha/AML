"""add raw_llm_response column to validation_result and sar

Revision ID: 011_raw_llm_response
Revises: 010_enrichment_snapshot
Create Date: 2026-05-22 23:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "011_raw_llm_response"
down_revision: Union[str, None] = "010_enrichment_snapshot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("validation_result", sa.Column("raw_llm_response", sa.String(), nullable=True))
    op.add_column("sar", sa.Column("raw_llm_response", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("sar", "raw_llm_response")
    op.drop_column("validation_result", "raw_llm_response")
