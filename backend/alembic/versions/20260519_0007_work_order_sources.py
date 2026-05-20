"""add work order rag sources

Revision ID: 20260519_0007
Revises: 20260519_0006
Create Date: 2026-05-19 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260519_0007"
down_revision: Union[str, None] = "20260519_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "work_order_sources",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "work_order_id",
            sa.BigInteger(),
            sa.ForeignKey("work_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("knowledge_chunk_id", sa.BigInteger(), sa.ForeignKey("knowledge_chunks.id"), nullable=False),
        sa.Column("source_label", sa.String(length=200), nullable=False),
        sa.Column("relevance_score", sa.Numeric(6, 4), nullable=False),
    )
    op.create_index("idx_work_order_sources_order", "work_order_sources", ["work_order_id"])
    op.create_index("idx_work_order_sources_chunk", "work_order_sources", ["knowledge_chunk_id"])


def downgrade() -> None:
    op.drop_index("idx_work_order_sources_chunk", table_name="work_order_sources")
    op.drop_index("idx_work_order_sources_order", table_name="work_order_sources")
    op.drop_table("work_order_sources")
