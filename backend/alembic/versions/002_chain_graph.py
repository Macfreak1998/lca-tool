"""chain graph replaces stages and slots

Revision ID: 002
Revises: 001
Create Date: 2026-09-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db import Base
from app import models  # noqa: F401

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DROP = (
    "slots",
    "stages",
    "configuration_extra_slots",
    "configuration_replaced_stages",
    "configuration_selections",
    "configuration_shares",
    "configuration_optional",
)


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in _DROP:
        if name in existing:
            op.drop_table(name)
    Base.metadata.create_all(bind=bind)
    if "configurations" in existing:
        op.execute(
            "UPDATE configurations SET invalid = 1, "
            "invalid_reason = 'Die Kettenstruktur hat sich geändert.'"
        )
    if "chains" in existing or "chains" in set(sa.inspect(bind).get_table_names()):
        op.execute(
            """
            INSERT INTO chain_nodes (
                chain_id, type, name, position_x, position_y, unit, optional, is_functional
            )
            SELECT c.id, 'product', e.name, 480, 180, c.end_unit, 0, 1
            FROM chains c
            JOIN end_products e ON e.id = c.end_product_id
            WHERE NOT EXISTS (
                SELECT 1 FROM chain_nodes n
                WHERE n.chain_id = c.id AND n.is_functional = 1
            )
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in (
        "chain_variants",
        "chain_edges",
        "chain_nodes",
        "configuration_replaced_nodes",
        "configuration_selections",
        "configuration_shares",
        "configuration_optional",
    ):
        if name in existing:
            op.drop_table(name)
