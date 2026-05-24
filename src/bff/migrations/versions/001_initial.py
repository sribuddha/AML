"""Initial schema — 7 tables with UUID PKs/FKs + source_txn_id.

Revision ID: 001_initial
Revises:
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer",
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("address_line", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("zip", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("customer_id"),
    )

    op.create_table(
        "account",
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("bank", sa.String(), nullable=True),
        sa.Column("date_opened", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("account_id"),
    )

    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=True),
        sa.Column("accepted_count", sa.Integer(), nullable=True),
        sa.Column("failed_count", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rejected_record",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("upload_id", sa.String(36), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=True),
        sa.Column("raw_data", sa.String(), nullable=True),
        sa.Column("reasons", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "transaction",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("upload_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("counterparty", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("date", sa.String(), nullable=True),
        sa.Column("source_txn_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rule",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("rules_json", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "validation_result",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("upload_id", sa.String(36), nullable=False),
        sa.Column("transaction_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("details", sa.String(), nullable=True),
        sa.Column("validated_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_rejected_upload", "rejected_record", ["upload_id"])
    op.create_index("idx_transaction_upload", "transaction", ["upload_id"])
    op.create_index("idx_transaction_account", "transaction", ["account_id"])
    op.create_index("idx_transaction_customer", "transaction", ["customer_id"])
    op.create_index("idx_validation_upload", "validation_result", ["upload_id"])
    op.create_index("idx_validation_tx", "validation_result", ["transaction_id"])


def downgrade() -> None:
    op.drop_index("idx_validation_tx", table_name="validation_result")
    op.drop_index("idx_validation_upload", table_name="validation_result")
    op.drop_index("idx_transaction_customer", table_name="transaction")
    op.drop_index("idx_transaction_account", table_name="transaction")
    op.drop_index("idx_transaction_upload", table_name="transaction")
    op.drop_index("idx_rejected_upload", table_name="rejected_record")

    op.drop_table("validation_result")
    op.drop_table("rule")
    op.drop_table("transaction")
    op.drop_table("rejected_record")
    op.drop_table("uploaded_files")
    op.drop_table("account")
    op.drop_table("customer")
