"""process nodes and combination rows replace variants

Revision ID: 003
Revises: 002
Create Date: 2026-09-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db import Base
from app import models  # noqa: F401

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DROP = (
    "chain_variants",
    "configuration_shares",
)


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in _DROP:
        if name in existing:
            op.drop_table(name)
    if "chain_nodes" in existing:
        columns = {column["name"] for column in sa.inspect(bind).get_columns("chain_nodes")}
        if "datasets_differ" not in columns:
            op.add_column(
                "chain_nodes",
                sa.Column("datasets_differ", sa.Boolean(), nullable=False, server_default=sa.false()),
            )
    Base.metadata.create_all(bind=bind)
    if "configurations" in existing:
        op.execute(
            "UPDATE configurations SET invalid = 1, "
            "invalid_reason = 'Die Kettenstruktur hat sich geändert.'"
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in (
        "chain_combination_amounts",
        "chain_combination_axes",
        "chain_combinations",
        "chain_dataset_shares",
        "configuration_shares",
    ):
        if name in existing:
            op.drop_table(name)
    if "chain_nodes" in existing:
        columns = {column["name"] for column in sa.inspect(bind).get_columns("chain_nodes")}
        if "datasets_differ" in columns:
            op.drop_column("chain_nodes", "datasets_differ")
