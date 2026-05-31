"""add_severity_to_rule

Revision ID: 1aa1b8a8d95c
Revises: 0de62f7f5f84
Create Date: 2026-05-31 09:37:52.928111

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1aa1b8a8d95c'
down_revision: Union[str, None] = '0de62f7f5f84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rule", sa.Column("severity", sa.String(), server_default="medium", nullable=True))


def downgrade() -> None:
    op.drop_column("rule", "severity")
