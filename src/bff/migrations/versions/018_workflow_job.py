"""create workflow_job table for durable workflow execution

Revision ID: 018_workflow_job
Revises: 017_source_txn_id_unique
Create Date: 2026-06-05 23:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "018_workflow_job"
down_revision: Union[str, None] = "017_source_txn_id_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_job",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("upload_id", sa.String(36), sa.ForeignKey("uploaded_files.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("mode", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workflow_job")
