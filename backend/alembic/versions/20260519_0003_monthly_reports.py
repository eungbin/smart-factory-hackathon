"""add monthly reports

Revision ID: 20260519_0003
Revises: 20260519_0002
Create Date: 2026-05-19 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260519_0003"
down_revision: Union[str, None] = "20260519_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "monthly_reports",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("factory_id", sa.BigInteger(), sa.ForeignKey("factories.id"), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("unplanned_downtime_hours", sa.Numeric(8, 2), nullable=False),
        sa.Column("prevented_count", sa.Integer(), nullable=False),
        sa.Column("mttr_minutes", sa.Numeric(8, 2), nullable=False),
        sa.Column("learning_data_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("factory_id", "month"),
    )

    op.create_table(
        "monthly_fault_distributions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("monthly_report_id", sa.BigInteger(), sa.ForeignKey("monthly_reports.id"), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )

    op.create_table(
        "knowhow_insights",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("factory_id", sa.BigInteger(), sa.ForeignKey("factories.id"), nullable=False),
        sa.Column("monthly_report_id", sa.BigInteger(), sa.ForeignKey("monthly_reports.id"), nullable=False),
        sa.Column("insight_type", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("icon", sa.String(length=20), nullable=True),
        sa.Column("equipment_label", sa.String(length=80), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("confidence_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("knowledge_key", sa.String(length=40), nullable=True),
        sa.Column("knowledge_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_knowhow_insights_report_type", "knowhow_insights", ["monthly_report_id", "insight_type"])


def downgrade() -> None:
    op.drop_index("idx_knowhow_insights_report_type", table_name="knowhow_insights")
    op.drop_table("knowhow_insights")
    op.drop_table("monthly_fault_distributions")
    op.drop_table("monthly_reports")
