"""initial core schema

Revision ID: 20260519_0001
Revises:
Create Date: 2026-05-19 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260519_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


equipment_status = postgresql.ENUM(
    "normal",
    "warn",
    "danger",
    name="equipment_status",
    create_type=False,
)
fault_type_code = postgresql.ENUM(
    "normal",
    "bearing_fault",
    "belt_loose",
    "rotor_unbalance",
    "shaft_misalignment",
    "hydraulic_seal",
    "other",
    name="fault_type_code",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    equipment_status.create(op.get_bind(), checkfirst=True)
    fault_type_code.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "factories",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("target_uptime_pct", sa.Numeric(5, 2), nullable=False, server_default="95.00"),
        sa.Column("target_delay_pct", sa.Numeric(5, 2), nullable=False, server_default="2.00"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("factory_id", sa.BigInteger(), sa.ForeignKey("factories.id"), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "equipment_models",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("maker", sa.String(length=80), nullable=True),
        sa.Column("model_name", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column(
            "default_thresholds",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("manual_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("model_name"),
    )

    op.create_table(
        "equipment",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("factory_id", sa.BigInteger(), sa.ForeignKey("factories.id"), nullable=False),
        sa.Column("model_id", sa.BigInteger(), sa.ForeignKey("equipment_models.id"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("serial_no", sa.String(length=80), nullable=True),
        sa.Column("installed_year", sa.Integer(), nullable=False),
        sa.Column("assigned_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("cumulative_runtime_hours", sa.Numeric(12, 1), nullable=True),
        sa.Column("thresholds_override", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("factory_id", "name"),
    )

    op.create_table(
        "equipment_state_latest",
        sa.Column("equipment_id", sa.BigInteger(), sa.ForeignKey("equipment.id"), primary_key=True),
        sa.Column("status", equipment_status, nullable=False),
        sa.Column("rul_hours", sa.Integer(), nullable=True),
        sa.Column("rul_lower_hours", sa.Integer(), nullable=True),
        sa.Column("rul_upper_hours", sa.Integer(), nullable=True),
        sa.Column("risk_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("fault_type_code", fault_type_code, nullable=True),
        sa.Column("fault_confidence_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("vibration_rms_g", sa.Numeric(8, 3), nullable=True),
        sa.Column("hydraulic_temp_c", sa.Numeric(8, 2), nullable=True),
        sa.Column("motor_current_a", sa.Numeric(8, 2), nullable=True),
        sa.Column("hydraulic_pressure_bar", sa.Numeric(8, 2), nullable=True),
        sa.Column("last_maintenance_at", sa.Date(), nullable=True),
        sa.Column("next_plan_text", sa.String(length=120), nullable=True),
        sa.Column("latest_sensor_reading_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("equipment_state_latest")
    op.drop_table("equipment")
    op.drop_table("equipment_models")
    op.drop_table("users")
    op.drop_table("factories")
    fault_type_code.drop(op.get_bind(), checkfirst=True)
    equipment_status.drop(op.get_bind(), checkfirst=True)
