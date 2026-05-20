"""add persisted work orders

Revision ID: 20260519_0005
Revises: 20260519_0004
Create Date: 2026-05-19 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260519_0005"
down_revision: Union[str, None] = "20260519_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "work_orders",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("equipment_id", sa.BigInteger(), sa.ForeignKey("equipment.id"), nullable=False),
        sa.Column("prediction_run_id", sa.BigInteger(), sa.ForeignKey("prediction_runs.id"), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="generated"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generator_provider", sa.String(length=40), nullable=False, server_default="template"),
        sa.Column("generator_model", sa.String(length=80), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("fault_type_text", sa.String(length=120), nullable=False),
        sa.Column("risk_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("rul_text", sa.String(length=80), nullable=False),
        sa.Column("source_summary", sa.String(length=255), nullable=False),
        sa.Column("total_minutes", sa.Integer(), nullable=False),
        sa.Column("tech_level", sa.String(length=80), nullable=False),
        sa.Column("caution", sa.Text(), nullable=False),
        sa.Column("raw_prompt", sa.Text(), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_work_orders_equipment_time", "work_orders", ["equipment_id", "generated_at"])
    op.create_index("idx_work_orders_prediction_run", "work_orders", ["prediction_run_id"])

    op.create_table(
        "work_order_steps",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "work_order_id",
            sa.BigInteger(),
            sa.ForeignKey("work_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("tool", sa.String(length=200), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("safety_required", sa.Boolean(), nullable=False),
    )
    op.create_index("idx_work_order_steps_order", "work_order_steps", ["work_order_id", "step_no"])

    op.create_table(
        "work_order_parts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "work_order_id",
            sa.BigInteger(),
            sa.ForeignKey("work_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("part_name", sa.String(length=160), nullable=False),
        sa.Column("qty_text", sa.String(length=80), nullable=False),
        sa.Column("stock_text", sa.String(length=80), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=True),
    )
    op.create_index("idx_work_order_parts_order", "work_order_parts", ["work_order_id"])


def downgrade() -> None:
    op.drop_index("idx_work_order_parts_order", table_name="work_order_parts")
    op.drop_table("work_order_parts")
    op.drop_index("idx_work_order_steps_order", table_name="work_order_steps")
    op.drop_table("work_order_steps")
    op.drop_index("idx_work_orders_prediction_run", table_name="work_orders")
    op.drop_index("idx_work_orders_equipment_time", table_name="work_orders")
    op.drop_table("work_orders")
