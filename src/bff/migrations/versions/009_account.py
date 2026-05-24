"""migrate account table to UUID pk + backfill

Revision ID: 009_account
Revises: 008_entity_status
Create Date: 2026-05-22 00:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '009_account'
down_revision: Union[str, None] = '008_entity_status'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add id column (nullable initially)
    op.add_column("account", sa.Column("id", sa.String(36), nullable=True))

    # Populate id with UUIDs for existing rows
    op.execute("UPDATE account SET id = lower(hex(randomblob(16))) WHERE id IS NULL")

    # Recreate table manually — batch mode can't cleanly replace a PK in SQLite
    op.create_table(
        "_account_new",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("account_id", sa.String, nullable=False, unique=True),
        sa.Column("name", sa.String, nullable=True),
        sa.Column("bank", sa.String, nullable=True),
        sa.Column("customer_id", sa.String, nullable=False),
        sa.Column("type", sa.String, nullable=True),
        sa.Column("date_opened", sa.String, nullable=True),
        sa.Column("created_at", sa.String, nullable=True),
        sa.Column("updated_at", sa.String, nullable=True),
    )

    op.execute("""
        INSERT INTO _account_new (id, account_id, name, bank, customer_id, type, date_opened, created_at, updated_at)
        SELECT id, account_id, name, bank, customer_id, type, date_opened, created_at, updated_at FROM account
    """)

    op.drop_table("account")
    op.rename_table("_account_new", "account")

    # Backfill new account rows from transaction table
    op.execute("""
        INSERT INTO account (id, account_id, customer_id, type, date_opened, created_at)
        SELECT
            lower(hex(randomblob(16))),
            t.account_id,
            t.customer_id,
            'checking',
            MIN(t.date),
            datetime('now')
        FROM "transaction" t
        WHERE NOT EXISTS (
            SELECT 1 FROM account a WHERE a.account_id = t.account_id
        )
        GROUP BY t.account_id, t.customer_id
    """)

    # Backfill new account rows from transaction table
    op.execute("""
        INSERT INTO account (id, account_id, customer_id, type, date_opened, created_at)
        SELECT
            lower(hex(randomblob(16))),
            t.account_id,
            t.customer_id,
            'checking',
            MIN(t.date),
            datetime('now')
        FROM "transaction" t
        WHERE NOT EXISTS (
            SELECT 1 FROM account a WHERE a.account_id = t.account_id
        )
        GROUP BY t.account_id, t.customer_id
    """)


def downgrade() -> None:
    op.drop_table("account")
