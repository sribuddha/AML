"""add upload_status, transaction_status; drop audit_log, ground_truth, txn.status

Creates two new append-only status tables, migrates existing audit_log data,
drops the old audit_log table, drops unused columns, and adds missing indexes.

Revision ID: 012_schema_cleanup
Revises: 011_raw_llm_response
Create Date: 2026-05-22 23:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012_schema_cleanup"
down_revision: Union[str, None] = "011_raw_llm_response"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _upgrade_data():
    conn = op.get_bind()

    # Maps upload event_type → status value
    conn.execute(sa.text("""
        INSERT INTO upload_status (upload_id, status, actor, created_at)
        SELECT
            entity_id AS upload_id,
            CASE event_type
                WHEN 'upload.processing' THEN 'processing'
                WHEN 'upload.completed' THEN 'complete'
                WHEN 'upload.failed' THEN 'failed'
                WHEN 'upload.pending_human' THEN 'pending_human'
                ELSE 'unknown'
            END AS status,
            actor,
            created_at
        FROM audit_log
        WHERE entity_type = 'upload'
    """))

    # Maps transaction event_type → derive status from payload JSON
    conn.execute(sa.text("""
        INSERT INTO transaction_status (transaction_id, status, actor, created_at)
        SELECT
            entity_id AS transaction_id,
            CASE
                WHEN event_type = 'transaction.reviewed' THEN json_extract(payload, '$.new_status')
                ELSE json_extract(payload, '$.status')
            END AS status,
            actor,
            created_at
        FROM audit_log
        WHERE entity_type = 'transaction'
    """))


def _downgrade_data():
    """Reverse data migration: reconstruct audit_log from status tables."""
    conn = op.get_bind()

    conn.execute(sa.text("""
        INSERT INTO audit_log (id, event_type, entity_type, entity_id, upload_id, payload, actor, created_at)
        SELECT
            hex(randomblob(16)),
            CASE status
                WHEN 'processing' THEN 'upload.processing'
                WHEN 'complete' THEN 'upload.completed'
                WHEN 'failed' THEN 'upload.failed'
                WHEN 'pending_human' THEN 'upload.pending_human'
            END,
            'upload',
            upload_id,
            upload_id,
            '{"status":"' || status || '"}',
            actor,
            created_at
        FROM upload_status
    """))

    conn.execute(sa.text("""
        INSERT INTO audit_log (id, event_type, entity_type, entity_id, upload_id, payload, actor, created_at)
        SELECT
            hex(randomblob(16)),
            CASE status
                WHEN 'flagged' THEN 'transaction.validated'
                WHEN 'escalated' THEN 'transaction.triaged'
                WHEN 'pending_review' THEN 'transaction.deep_analysed'
                WHEN 'confirmed' THEN 'transaction.reviewed'
                WHEN 'dismissed' THEN 'transaction.reviewed'
                ELSE 'transaction.' || status
            END,
            'transaction',
            transaction_id,
            (SELECT upload_id FROM "transaction" WHERE id = transaction_id),
            '{"status":"' || status || '"}',
            actor,
            created_at
        FROM transaction_status
    """))


def upgrade() -> None:
    # ### Create upload_status table ###
    op.create_table(
        "upload_status",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("upload_id", sa.String(36), sa.ForeignKey("uploaded_files.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False, server_default="system"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_upload_status_upload", "upload_status", ["upload_id", "created_at"])

    # ### Create transaction_status table ###
    op.create_table(
        "transaction_status",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("transaction_id", sa.String(36), sa.ForeignKey("transaction.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False, server_default="system"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_transaction_status_tx", "transaction_status", ["transaction_id", "created_at"])

    # ### Migrate data from audit_log ###
    _upgrade_data()

    # ### Drop audit_log table ###
    op.drop_table("audit_log")

    # ### Drop unused columns from transaction ###
    with op.batch_alter_table("transaction") as batch_op:
        batch_op.drop_column("ground_truth")
        batch_op.drop_column("status")

    # ### Add indexes on sar FK columns ###
    with op.batch_alter_table("sar") as batch_op:
        batch_op.create_index("idx_sar_upload", ["upload_id"])
        batch_op.create_index("idx_sar_transaction", ["transaction_id"])
        batch_op.create_index("idx_sar_rule", ["rule_id"])

    # ### Fix account.name: NOT NULL → nullable ###
    with op.batch_alter_table("account") as batch_op:
        batch_op.alter_column("name", nullable=True)


def downgrade() -> None:
    # ### Restore account.name nullability ###
    with op.batch_alter_table("account") as batch_op:
        batch_op.alter_column("name", nullable=False)

    # ### Drop sar indexes ###
    with op.batch_alter_table("sar") as batch_op:
        batch_op.drop_index("idx_sar_upload")
        batch_op.drop_index("idx_sar_transaction")
        batch_op.drop_index("idx_sar_rule")

    # ### Restore transaction columns ###
    with op.batch_alter_table("transaction") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(), nullable=False, server_default="loaded"))
        batch_op.add_column(sa.Column("ground_truth", sa.String(), nullable=True))

    # ### Recreate audit_log ###
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("upload_id", sa.String(36), sa.ForeignKey("uploaded_files.id"), nullable=True),
        sa.Column("payload", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False, server_default="system"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_log_upload", "audit_log", ["upload_id"])
    op.create_index("idx_audit_log_event", "audit_log", ["event_type"])
    op.create_index("idx_audit_log_entity", "audit_log", ["entity_type", "entity_id"])

    # ### Reverse data migration ###
    _downgrade_data()

    # ### Drop new tables ###
    op.drop_table("transaction_status")
    op.drop_table("upload_status")
