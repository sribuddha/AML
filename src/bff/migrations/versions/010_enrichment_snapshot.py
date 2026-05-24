"""add enrichment_snapshot table for eval audit trail

Revision ID: 010_enrichment_snapshot
Revises: 009_account
Create Date: 2026-05-22 01:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '010_enrichment_snapshot'
down_revision: Union[str, None] = '009_account'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enrichment_snapshot",
        sa.Column("upload_id", sa.String(36), primary_key=True),
        sa.Column("customer_id", sa.String(), primary_key=True),
        sa.Column("ref_date", sa.String(), nullable=False),
        sa.Column("customer_txn_count_30d", sa.Integer(), nullable=False),
        sa.Column("customer_sum_30d", sa.Float(), nullable=False),
        sa.Column("customer_avg_30d", sa.Float(), nullable=False),
        sa.Column("customer_std_amt_30d", sa.Float(), nullable=True),
        sa.Column("account_type", sa.String(), nullable=True),
        sa.Column("account_age_days", sa.Integer(), nullable=True),
        sa.Column("structuring_24h_count", sa.Integer(), nullable=False),
        sa.Column("velocity_zscore", sa.Float(), nullable=True),
        sa.Column("dormancy_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_enrichment_snapshot_upload", "enrichment_snapshot", ["upload_id"])
    op.create_index("idx_enrichment_snapshot_customer", "enrichment_snapshot", ["customer_id"])


def downgrade() -> None:
    op.drop_index("idx_enrichment_snapshot_upload")
    op.drop_index("idx_enrichment_snapshot_customer")
    op.drop_table("enrichment_snapshot")
