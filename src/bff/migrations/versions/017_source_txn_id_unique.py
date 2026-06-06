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
    op.create_unique_constraint("uq_transaction_source_txn_id", "transaction", ["source_txn_id"])


def downgrade() -> None:
    op.drop_constraint("uq_transaction_source_txn_id", "transaction", type_="unique")
