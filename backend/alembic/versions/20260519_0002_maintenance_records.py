"""add maintenance records and learning queue

Revision ID: 20260519_0002
Revises: 20260519_0001
Create Date: 2026-05-19 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260519_0002"
down_revision: Union[str, None] = "20260519_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "maintenance_records",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("equipment_id", sa.BigInteger(), sa.ForeignKey("equipment.id"), nullable=False),
        sa.Column("work_order_id", sa.BigInteger(), nullable=True),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("technician_name", sa.String(length=80), nullable=False),
        sa.Column("maintenance_type", sa.String(length=40), nullable=False),
        sa.Column("result", sa.String(length=40), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("parts_text", sa.String(length=255), nullable=True),
        sa.Column("actions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("actual_fault_type_code", sa.String(length=60), nullable=True),
        sa.Column("ai_accuracy_note", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("next_plan_text", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_maintenance_records_equipment_time", "maintenance_records", ["equipment_id", "performed_at"])

    op.create_table(
        "learning_queue",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("queue_key", sa.String(length=40), nullable=False, unique=True),
        sa.Column("equipment_id", sa.BigInteger(), sa.ForeignKey("equipment.id"), nullable=False),
        sa.Column("maintenance_record_id", sa.BigInteger(), sa.ForeignKey("maintenance_records.id"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("label_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_learning_queue_equipment", "learning_queue", ["equipment_id"])


def downgrade() -> None:
    op.drop_index("idx_learning_queue_equipment", table_name="learning_queue")
    op.drop_table("learning_queue")
    op.drop_index("idx_maintenance_records_equipment_time", table_name="maintenance_records")
    op.drop_table("maintenance_records")
