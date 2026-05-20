from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


AssetStatus = Literal["normal", "watch", "critical"]


class SensorReading(BaseModel):
    key: str
    label: str
    unit: str
    baseline: float
    current: float
    change_pct: float
    contribution: float
    series: list[float]


class AssetSummary(BaseModel):
    asset_id: str
    name: str
    machine_type: str
    location: str
    status: AssetStatus
    rul_hours: int
    risk_72h: float
    anomaly_score: float
    last_update: datetime
    primary_issue: str
    recommended_action: str
    sparkline: list[float]


class AssetDetail(AssetSummary):
    model_version: str
    confidence_interval: tuple[int, int]
    sensors: list[SensorReading]
    sensor_window: list[dict[str, float]]
    recent_events: list[dict[str, Any]]


class PredictRequest(BaseModel):
    asset_id: str | None = Field(default=None, description="If omitted, INJ-03 demo asset is used.")
    window: list[dict[str, float]] | None = None


class PredictResponse(BaseModel):
    asset_id: str
    model_version: str
    rul_hours: int
    risk_72h: float
    confidence_interval: tuple[int, int]
    anomaly_score: float
    contributing_sensors: list[SensorReading]
    dataset_roles: dict[str, str]
    generated_at: datetime
    rul_source: str = "factory-sim"
    rul_unit: str = "hours"
    cmapss_subset: str | None = None
    cmapss_unit: int | None = None
    cmapss_last_cycle: int | None = None
    cmapss_actual_rul_reference: float | None = None


class FaultClassProbability(BaseModel):
    code: str
    label: str
    probability: float


class FaultClassificationResponse(BaseModel):
    asset_id: str
    model_version: str
    fault_code: str
    fault_label: str
    fault_probability: float
    is_fault: bool
    top_classes: list[FaultClassProbability]
    evidence: list[str]
    source: str
    generated_at: datetime


class HealthPredictionResponse(BaseModel):
    asset_id: str
    rul: PredictResponse
    fault: FaultClassificationResponse
    generated_at: datetime


class WorkOrderCreate(BaseModel):
    asset_id: str
    prediction: PredictResponse | None = None
    requested_by: str = "김영수 반장"


class WorkOrder(BaseModel):
    id: str
    asset_id: str
    asset_name: str
    severity: AssetStatus
    status: Literal["draft", "dispatched", "closed"]
    generated_at: datetime
    requested_by: str
    summary: str
    root_cause_hypothesis: str
    inspection_points: list[str]
    tools: list[str]
    consumables: list[str]
    estimated_minutes: int
    safety_rules: list[str]
    checklist: list[str]
    manual_sources: list[dict[str, str]]
    dispatch_message: str


class DispatchResponse(BaseModel):
    work_order_id: str
    channel: str
    recipient_group: str
    preview: str
    dispatched_at: datetime


class MaintenanceEventCreate(BaseModel):
    work_order_id: str | None = None
    asset_id: str
    worker: str = "정비 작업자"
    result: str
    parts_replaced: str = ""
    downtime_minutes: int = 0
    comments: str = ""
    follow_up_needed: bool = False


class MaintenanceEvent(MaintenanceEventCreate):
    id: str
    created_at: datetime
    training_queue_id: str


class KnowledgeReport(BaseModel):
    month: str
    digitized_knowhow_count: int
    training_queue_count: int
    estimated_downtime_prevented_hours: float
    work_order_time_saved_minutes: int
    top_failure_modes: list[dict[str, Any]]
    recent_events: list[MaintenanceEvent]
    dataset_notes: dict[str, str]
