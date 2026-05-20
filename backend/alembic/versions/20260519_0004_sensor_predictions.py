"""add sensor readings and prediction runs

Revision ID: 20260519_0004
Revises: 20260519_0003
Create Date: 2026-05-19 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260519_0004"
down_revision: Union[str, None] = "20260519_0003"
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
    op.create_table(
        "sensor_readings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("equipment_id", sa.BigInteger(), sa.ForeignKey("equipment.id"), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("vibration_rms_g", sa.Numeric(8, 3), nullable=False),
        sa.Column("hydraulic_temp_c", sa.Numeric(8, 2), nullable=False),
        sa.Column("motor_current_a", sa.Numeric(8, 2), nullable=False),
        sa.Column("hydraulic_pressure_bar", sa.Numeric(8, 2), nullable=False),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="backend_simulator"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_sensor_readings_equipment_time", "sensor_readings", ["equipment_id", "measured_at"])

    op.create_table(
        "prediction_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("equipment_id", sa.BigInteger(), sa.ForeignKey("equipment.id"), nullable=False),
        sa.Column("input_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_readings_count", sa.Integer(), nullable=False),
        sa.Column("status", equipment_status, nullable=False),
        sa.Column("rul_hours", sa.Integer(), nullable=False),
        sa.Column("rul_lower_hours", sa.Integer(), nullable=False),
        sa.Column("rul_upper_hours", sa.Integer(), nullable=False),
        sa.Column("risk_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("fault_type_code", fault_type_code, nullable=True),
        sa.Column("fault_confidence_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_prediction_runs_equipment_time", "prediction_runs", ["equipment_id", "created_at"])

    op.create_table(
        "prediction_fault_probabilities",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "prediction_run_id",
            sa.BigInteger(),
            sa.ForeignKey("prediction_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fault_type_code", fault_type_code, nullable=False),
        sa.Column("probability_pct", sa.Numeric(5, 2), nullable=False),
    )
    op.create_index(
        "idx_prediction_fault_probabilities_run",
        "prediction_fault_probabilities",
        ["prediction_run_id"],
    )

    op.create_table(
        "prediction_root_causes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "prediction_run_id",
            sa.BigInteger(),
            sa.ForeignKey("prediction_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sensor_name", sa.String(length=80), nullable=False),
        sa.Column("importance_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("display_text", sa.String(length=120), nullable=False),
        sa.Column("rank_no", sa.Integer(), nullable=False),
    )
    op.create_index("idx_prediction_root_causes_run", "prediction_root_causes", ["prediction_run_id"])

    op.add_column("equipment_state_latest", sa.Column("latest_prediction_run_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("equipment_state_latest", "latest_prediction_run_id")
    op.drop_index("idx_prediction_root_causes_run", table_name="prediction_root_causes")
    op.drop_table("prediction_root_causes")
    op.drop_index("idx_prediction_fault_probabilities_run", table_name="prediction_fault_probabilities")
    op.drop_table("prediction_fault_probabilities")
    op.drop_index("idx_prediction_runs_equipment_time", table_name="prediction_runs")
    op.drop_table("prediction_runs")
    op.drop_index("idx_sensor_readings_equipment_time", table_name="sensor_readings")
    op.drop_table("sensor_readings")
