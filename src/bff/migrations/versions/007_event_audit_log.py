"""Migrate audit_log to event-sourcing schema.

Revision ID: 007_event_audit_log
"""
import sqlalchemy as sa
from alembic import op

revision: str = "007_event_audit_log"
down_revision: str = "006_audit_log"


def upgrade():
    op.drop_table("audit_log")
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("entity_type", sa.String, nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("upload_id", sa.String(36), sa.ForeignKey("uploaded_files.id"), nullable=True),
        sa.Column("payload", sa.String, nullable=False),
        sa.Column("actor", sa.String, nullable=False, server_default="system"),
        sa.Column("created_at", sa.String, nullable=False),
    )
    op.create_index("idx_audit_log_upload", "audit_log", ["upload_id"])
    op.create_index("idx_audit_log_event", "audit_log", ["event_type"])
    op.create_index("idx_audit_log_entity", "audit_log", ["entity_type", "entity_id"])


def downgrade():
    op.drop_index("idx_audit_log_entity", table_name="audit_log")
    op.drop_index("idx_audit_log_event", table_name="audit_log")
    op.drop_index("idx_audit_log_upload", table_name="audit_log")
    op.drop_table("audit_log")
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("upload_id", sa.String(36), sa.ForeignKey("uploaded_files.id"), nullable=False),
        sa.Column("transaction_id", sa.String(36), sa.ForeignKey("transaction.id"), nullable=False),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("old_values", sa.String, nullable=True),
        sa.Column("new_values", sa.String, nullable=False),
        sa.Column("changed_by", sa.String, nullable=False, server_default="system"),
        sa.Column("created_at", sa.String, nullable=True),
    )
    op.create_index("idx_audit_log_upload", "audit_log", ["upload_id"])
