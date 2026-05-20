from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class EquipmentStatus(str, Enum):
    normal = "normal"
    warn = "warn"
    danger = "danger"


class FaultTypeCode(str, Enum):
    normal = "normal"
    bearing_fault = "bearing_fault"
    belt_loose = "belt_loose"
    rotor_unbalance = "rotor_unbalance"
    shaft_misalignment = "shaft_misalignment"
    hydraulic_seal = "hydraulic_seal"
    other = "other"


equipment_status_type = postgresql.ENUM(
    EquipmentStatus,
    name="equipment_status",
    create_type=False,
)
fault_type_code_type = postgresql.ENUM(
    FaultTypeCode,
    name="fault_type_code",
    create_type=False,
)


class Factory(Base):
    __tablename__ = "factories"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(100))
    address: Mapped[str | None] = mapped_column(sa.String(255))
    industry: Mapped[str | None] = mapped_column(sa.String(100))
    target_uptime_pct: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2))
    target_delay_pct: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    factory_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("factories.id"))
    name: Mapped[str] = mapped_column(sa.String(50))
    role: Mapped[str] = mapped_column(sa.String(30))
    phone: Mapped[str | None] = mapped_column(sa.String(30))
    is_active: Mapped[bool] = mapped_column(sa.Boolean)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


class EquipmentModel(Base):
    __tablename__ = "equipment_models"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    maker: Mapped[str | None] = mapped_column(sa.String(80))
    model_name: Mapped[str] = mapped_column(sa.String(80))
    category: Mapped[str] = mapped_column(sa.String(50))
    default_thresholds: Mapped[dict[str, Any]] = mapped_column(postgresql.JSONB)
    manual_notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    factory_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("factories.id"))
    model_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("equipment_models.id"))
    name: Mapped[str] = mapped_column(sa.String(80))
    serial_no: Mapped[str | None] = mapped_column(sa.String(80))
    installed_year: Mapped[int] = mapped_column(sa.Integer)
    assigned_user_id: Mapped[int | None] = mapped_column(sa.BigInteger, sa.ForeignKey("users.id"))
    cumulative_runtime_hours: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 1))
    thresholds_override: Mapped[dict[str, Any] | None] = mapped_column(postgresql.JSONB)
    is_active: Mapped[bool] = mapped_column(sa.Boolean)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


class EquipmentStateLatest(Base):
    __tablename__ = "equipment_state_latest"

    equipment_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("equipment.id"), primary_key=True)
    status: Mapped[EquipmentStatus] = mapped_column(equipment_status_type)
    rul_hours: Mapped[int | None] = mapped_column(sa.Integer)
    rul_lower_hours: Mapped[int | None] = mapped_column(sa.Integer)
    rul_upper_hours: Mapped[int | None] = mapped_column(sa.Integer)
    risk_pct: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2))
    fault_type_code: Mapped[FaultTypeCode | None] = mapped_column(fault_type_code_type)
    fault_confidence_pct: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 2))
    vibration_rms_g: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 3))
    hydraulic_temp_c: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2))
    motor_current_a: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2))
    hydraulic_pressure_bar: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2))
    last_maintenance_at: Mapped[date | None] = mapped_column(sa.Date)
    next_plan_text: Mapped[str | None] = mapped_column(sa.String(120))
    latest_sensor_reading_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    latest_prediction_run_id: Mapped[int | None] = mapped_column(sa.BigInteger)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("equipment.id"))
    measured_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    vibration_rms_g: Mapped[Decimal] = mapped_column(sa.Numeric(8, 3))
    hydraulic_temp_c: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2))
    motor_current_a: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2))
    hydraulic_pressure_bar: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2))
    features: Mapped[dict[str, Any] | None] = mapped_column(postgresql.JSONB)
    source: Mapped[str] = mapped_column(sa.String(30))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


class PredictionRun(Base):
    __tablename__ = "prediction_runs"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("equipment.id"))
    input_window_start: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    input_window_end: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    input_readings_count: Mapped[int] = mapped_column(sa.Integer)
    status: Mapped[EquipmentStatus] = mapped_column(equipment_status_type)
    rul_hours: Mapped[int] = mapped_column(sa.Integer)
    rul_lower_hours: Mapped[int] = mapped_column(sa.Integer)
    rul_upper_hours: Mapped[int] = mapped_column(sa.Integer)
    risk_pct: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2))
    fault_type_code: Mapped[FaultTypeCode | None] = mapped_column(fault_type_code_type)
    fault_confidence_pct: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 2))
    summary: Mapped[str | None] = mapped_column(sa.Text)
    raw_output: Mapped[dict[str, Any] | None] = mapped_column(postgresql.JSONB)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


class PredictionFaultProbability(Base):
    __tablename__ = "prediction_fault_probabilities"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    prediction_run_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("prediction_runs.id", ondelete="CASCADE"))
    fault_type_code: Mapped[FaultTypeCode] = mapped_column(fault_type_code_type)
    probability_pct: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2))


class PredictionRootCause(Base):
    __tablename__ = "prediction_root_causes"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    prediction_run_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("prediction_runs.id", ondelete="CASCADE"))
    sensor_name: Mapped[str] = mapped_column(sa.String(80))
    importance_pct: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2))
    direction: Mapped[str] = mapped_column(sa.String(20))
    display_text: Mapped[str] = mapped_column(sa.String(120))
    rank_no: Mapped[int] = mapped_column(sa.Integer)


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("equipment.id"))
    prediction_run_id: Mapped[int | None] = mapped_column(sa.BigInteger, sa.ForeignKey("prediction_runs.id"))
    status: Mapped[str] = mapped_column(sa.String(30))
    generated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    generator_provider: Mapped[str] = mapped_column(sa.String(40))
    generator_model: Mapped[str | None] = mapped_column(sa.String(80))
    title: Mapped[str] = mapped_column(sa.String(200))
    fault_type_text: Mapped[str] = mapped_column(sa.String(120))
    risk_pct: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2))
    rul_text: Mapped[str] = mapped_column(sa.String(80))
    source_summary: Mapped[str] = mapped_column(sa.String(255))
    total_minutes: Mapped[int] = mapped_column(sa.Integer)
    tech_level: Mapped[str] = mapped_column(sa.String(80))
    caution: Mapped[str] = mapped_column(sa.Text)
    raw_prompt: Mapped[str | None] = mapped_column(sa.Text)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(postgresql.JSONB)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


class WorkOrderStep(Base):
    __tablename__ = "work_order_steps"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("work_orders.id", ondelete="CASCADE"))
    step_no: Mapped[int] = mapped_column(sa.Integer)
    category: Mapped[str] = mapped_column(sa.String(20))
    action: Mapped[str] = mapped_column(sa.Text)
    tool: Mapped[str] = mapped_column(sa.String(200))
    estimated_minutes: Mapped[int] = mapped_column(sa.Integer)
    safety_required: Mapped[bool] = mapped_column(sa.Boolean)


class WorkOrderPart(Base):
    __tablename__ = "work_order_parts"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("work_orders.id", ondelete="CASCADE"))
    part_name: Mapped[str] = mapped_column(sa.String(160))
    qty_text: Mapped[str] = mapped_column(sa.String(80))
    stock_text: Mapped[str] = mapped_column(sa.String(80))
    is_available: Mapped[bool | None] = mapped_column(sa.Boolean)


class WorkOrderSource(Base):
    __tablename__ = "work_order_sources"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("work_orders.id", ondelete="CASCADE"))
    knowledge_chunk_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("knowledge_chunks.id"))
    source_label: Mapped[str] = mapped_column(sa.String(200))
    relevance_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 4))


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    factory_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("factories.id"))
    title: Mapped[str] = mapped_column(sa.String(200))
    document_type: Mapped[str] = mapped_column(sa.String(30))
    equipment_model_id: Mapped[int | None] = mapped_column(sa.BigInteger, sa.ForeignKey("equipment_models.id"))
    file_name: Mapped[str | None] = mapped_column(sa.String(255))
    file_uri: Mapped[str | None] = mapped_column(sa.Text)
    source_label: Mapped[str] = mapped_column(sa.String(200))
    uploaded_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"))
    chunk_no: Mapped[int] = mapped_column(sa.Integer)
    heading: Mapped[str | None] = mapped_column(sa.String(200))
    body: Mapped[str] = mapped_column(sa.Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(768))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", postgresql.JSONB)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("equipment.id"))
    work_order_id: Mapped[int | None] = mapped_column(sa.BigInteger)
    performed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    technician_name: Mapped[str] = mapped_column(sa.String(80))
    maintenance_type: Mapped[str] = mapped_column(sa.String(40))
    result: Mapped[str] = mapped_column(sa.String(40))
    duration_minutes: Mapped[int] = mapped_column(sa.Integer)
    parts_text: Mapped[str | None] = mapped_column(sa.String(255))
    actions: Mapped[dict[str, Any]] = mapped_column(postgresql.JSONB)
    actual_fault_type_code: Mapped[str | None] = mapped_column(sa.String(60))
    ai_accuracy_note: Mapped[str | None] = mapped_column(sa.Text)
    note: Mapped[str | None] = mapped_column(sa.Text)
    next_plan_text: Mapped[str | None] = mapped_column(sa.String(120))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


class LearningQueue(Base):
    __tablename__ = "learning_queue"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    queue_key: Mapped[str] = mapped_column(sa.String(40), unique=True)
    equipment_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("equipment.id"))
    maintenance_record_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("maintenance_records.id"))
    status: Mapped[str] = mapped_column(sa.String(30))
    label_payload: Mapped[dict[str, Any]] = mapped_column(postgresql.JSONB)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


class MonthlyReport(Base):
    __tablename__ = "monthly_reports"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    factory_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("factories.id"))
    month: Mapped[date] = mapped_column(sa.Date)
    unplanned_downtime_hours: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2))
    prevented_count: Mapped[int] = mapped_column(sa.Integer)
    mttr_minutes: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2))
    learning_data_count: Mapped[int] = mapped_column(sa.Integer)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


class MonthlyFaultDistribution(Base):
    __tablename__ = "monthly_fault_distributions"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    monthly_report_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("monthly_reports.id"))
    display_name: Mapped[str] = mapped_column(sa.String(80))
    percentage: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2))
    color: Mapped[str] = mapped_column(sa.String(20))
    sort_order: Mapped[int] = mapped_column(sa.Integer)


class KnowhowInsight(Base):
    __tablename__ = "knowhow_insights"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    factory_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("factories.id"))
    monthly_report_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("monthly_reports.id"))
    insight_type: Mapped[str] = mapped_column(sa.String(30))
    priority: Mapped[str] = mapped_column(sa.String(20))
    icon: Mapped[str | None] = mapped_column(sa.String(20))
    equipment_label: Mapped[str | None] = mapped_column(sa.String(80))
    title: Mapped[str] = mapped_column(sa.String(160))
    body: Mapped[str] = mapped_column(sa.Text)
    confidence_pct: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 2))
    knowledge_key: Mapped[str | None] = mapped_column(sa.String(40))
    knowledge_date: Mapped[date | None] = mapped_column(sa.Date)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"))
