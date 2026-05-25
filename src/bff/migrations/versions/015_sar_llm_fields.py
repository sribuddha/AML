"""add llm_confidence, triage_reasoning, triage_stage to sar

Revision ID: 015_sar_llm_fields
Revises: 014_eval_file
Create Date: 2026-05-24 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015_sar_llm_fields"
down_revision: Union[str, None] = "014_eval_file"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sar", sa.Column("llm_confidence", sa.Float(), nullable=True))
    op.add_column("sar", sa.Column("triage_reasoning", sa.String(), nullable=True))
    op.add_column("sar", sa.Column("triage_stage", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("sar", "triage_stage")
    op.drop_column("sar", "triage_reasoning")
    op.drop_column("sar", "llm_confidence")
