"""add transaction.status, merge upload review_status into status

Revision ID: 008_entity_status
Revises: 007_event_audit_log
Create Date: 2026-05-21 23:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '008_entity_status'
down_revision: Union[str, None] = '007_event_audit_log'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add status column to transaction
    op.add_column("transaction", sa.Column("status", sa.String(), nullable=False, server_default="loaded"))

    # Merge review_status into status for uploaded_files
    # New unified status values: uploaded, processing, pending_human, complete, failed, committed
    # Old review_status: NULL, PROGRESS, PENDING_HUMAN, COMPLETE
    # Old status: processing, completed, failed, committed
    with op.batch_alter_table("uploaded_files") as batch_op:
        batch_op.add_column(sa.Column("_unified_status", sa.String(), nullable=False, server_default="uploaded"))

    conn = op.get_bind()
    conn.exec_driver_sql("""
        UPDATE uploaded_files
        SET _unified_status = CASE
            WHEN status = 'failed' THEN 'failed'
            WHEN review_status = 'COMPLETE' THEN 'complete'
            WHEN review_status = 'PENDING_HUMAN' THEN 'pending_human'
            WHEN review_status = 'PROGRESS' THEN 'processing'
            WHEN status = 'processing' THEN 'processing'
            WHEN status = 'committed' THEN 'committed'
            ELSE 'uploaded'
        END
    """)

    with op.batch_alter_table("uploaded_files") as batch_op:
        batch_op.drop_column("status")
        batch_op.drop_column("review_status")
        batch_op.alter_column("_unified_status", new_column_name="status")


def downgrade() -> None:
    with op.batch_alter_table("uploaded_files") as batch_op:
        batch_op.add_column(sa.Column("_old_status", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("review_status", sa.String(), nullable=True))

    conn = op.get_bind()
    conn.exec_driver_sql("""
        UPDATE uploaded_files
        SET _old_status = CASE
            WHEN status = 'complete' THEN 'completed'
            WHEN status = 'uploaded' THEN 'completed'
            WHEN status = 'failed' THEN 'failed'
            WHEN status = 'processing' THEN 'processing'
            WHEN status = 'committed' THEN 'committed'
            ELSE 'completed'
        END,
        review_status = CASE
            WHEN status = 'complete' THEN 'COMPLETE'
            WHEN status = 'pending_human' THEN 'PENDING_HUMAN'
            WHEN status = 'processing' THEN 'PROGRESS'
            ELSE NULL
        END
    """)

    with op.batch_alter_table("uploaded_files") as batch_op:
        batch_op.drop_column("status")
        batch_op.alter_column("_old_status", new_column_name="status")
        batch_op.alter_column("review_status", new_column_name="review_status")

    op.drop_column("transaction", "status")
