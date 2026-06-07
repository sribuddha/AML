"""replace global unique on source_txn_id with composite (upload_id, source_txn_id)

Revision ID: 019_source_txn_id_upload_unique
Revises: 018_workflow_job
Create Date: 2026-06-05 23:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "019_source_txn_id_upload_unique"
down_revision: Union[str, None] = "018_workflow_job"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("transaction") as batch_op:
        batch_op.drop_constraint("uq_transaction_source_txn_id", type_="unique")
        batch_op.create_unique_constraint("uq_transaction_upload_source", ["upload_id", "source_txn_id"])


def downgrade() -> None:
    with op.batch_alter_table("transaction") as batch_op:
        batch_op.drop_constraint("uq_transaction_upload_source", type_="unique")
        batch_op.create_unique_constraint("uq_transaction_source_txn_id", ["source_txn_id"])
