"""add unique constraint on transaction.source_txn_id

Revision ID: 017_source_txn_id_unique
Revises: 016_sar_version_locking
Create Date: 2026-06-05 23:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "017_source_txn_id_unique"
down_revision: Union[str, None] = "016_sar_version_locking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            UPDATE "transaction"
            SET source_txn_id = NULL
            WHERE rowid NOT IN (
                SELECT MIN(rowid) FROM "transaction" GROUP BY source_txn_id
            )
            AND source_txn_id IS NOT NULL
        """)
    )
    with op.batch_alter_table("transaction") as batch_op:
        batch_op.create_unique_constraint("uq_transaction_source_txn_id", ["source_txn_id"])


def downgrade() -> None:
    with op.batch_alter_table("transaction") as batch_op:
        batch_op.drop_constraint("uq_transaction_source_txn_id", type_="unique")
