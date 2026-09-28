"""Sollmenge, Effizienz und Allokationsanteil

Revision ID: 004
Revises: 003
Create Date: 2026-09-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    edge_columns = {column["name"] for column in sa.inspect(bind).get_columns("chain_edges")}
    if "allocation_share" not in edge_columns:
        op.add_column("chain_edges", sa.Column("allocation_share", sa.Float(), nullable=True))
    amount_columns = {column["name"] for column in sa.inspect(bind).get_columns("chain_combination_amounts")}
    if "efficiency" not in amount_columns:
        op.add_column(
            "chain_combination_amounts",
            sa.Column("efficiency", sa.Float(), nullable=False, server_default="1"),
        )
    op.execute(
        """
        UPDATE chain_combination_amounts
        SET efficiency = 1.0 / input_amount,
            input_amount = 1.0
        WHERE input_amount > 1
          AND EXISTS (
            SELECT 1
            FROM chain_edges AS edge
            JOIN chain_combinations AS combo ON combo.id = chain_combination_amounts.combination_id
            WHERE edge.source_id = chain_combination_amounts.category_node_id
              AND edge.target_id = combo.process_node_id
              AND edge.kind = 'material'
          )
        """
    )
    op.execute(
        """
        UPDATE chain_edges
        SET efficiency = 1.0 / input_amount,
            input_amount = 1.0
        WHERE kind = 'material' AND input_amount > 1
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    edge_columns = {column["name"] for column in sa.inspect(bind).get_columns("chain_edges")}
    if "allocation_share" in edge_columns:
        op.drop_column("chain_edges", "allocation_share")
    amount_columns = {column["name"] for column in sa.inspect(bind).get_columns("chain_combination_amounts")}
    if "efficiency" in amount_columns:
        op.drop_column("chain_combination_amounts", "efficiency")
