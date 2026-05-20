from dataclasses import dataclass
from datetime import datetime

from app.db.models import EquipmentStatus, FaultTypeCode


@dataclass(frozen=True)
class SensorPoint:
    measured_at: datetime
    vibration_rms_g: float
    hydraulic_temp_c: float
    motor_current_a: float
    hydraulic_pressure_bar: float


@dataclass(frozen=True)
class SensorWindow:
    equipment_id: int
    points: list[SensorPoint]


@dataclass(frozen=True)
class FaultProbability:
    fault_type_code: FaultTypeCode
    probability_pct: int


@dataclass(frozen=True)
class RootSensor:
    sensor_name: str
    importance_pct: int
    direction: str
    display_text: str


@dataclass(frozen=True)
class InferenceResult:
    status: EquipmentStatus
    rul_hours: int
    rul_lower_hours: int
    rul_upper_hours: int
    risk_pct: int
    fault_type_code: FaultTypeCode | None
    fault_confidence_pct: int | None
    fault_probabilities: list[FaultProbability]
    root_sensors: list[RootSensor]
    summary: str
    raw_output: dict[str, object]
