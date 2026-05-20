from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import sin

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Equipment, EquipmentStateLatest, SensorReading
from app.schemas.predictions import PredictionOut
from app.schemas.simulation import SimulationTickOut
from app.services.predictions import create_prediction_run


KST = timezone(timedelta(hours=9))


def create_sensor_tick(
    db: Session,
    factory_id: int = 1,
    equipment_id: int | None = None,
    window_hours: int = 24,
    include_predictions: bool = True,
) -> SimulationTickOut:
    rows = _load_target_states(db, factory_id, equipment_id)
    predictions: list[PredictionOut] = []

    for equipment, state in rows:
        measured_at = datetime.now(KST)
        reading_count = db.scalar(select(func.count()).where(SensorReading.equipment_id == equipment.id)) or 0
        reading = _next_reading(equipment.id, state, measured_at, reading_count)
        db.add(reading)
        state.vibration_rms_g = reading.vibration_rms_g
        state.hydraulic_temp_c = reading.hydraulic_temp_c
        state.motor_current_a = reading.motor_current_a
        state.hydraulic_pressure_bar = reading.hydraulic_pressure_bar
        state.latest_sensor_reading_at = measured_at
        state.updated_at = measured_at
        db.flush()

        if include_predictions:
            prediction = create_prediction_run(db, equipment.id, window_hours=window_hours, commit=False)
            if prediction is not None:
                predictions.append(prediction)

    db.commit()
    return SimulationTickOut(insertedReadings=len(rows), predictions=predictions)


def _load_target_states(
    db: Session,
    factory_id: int,
    equipment_id: int | None,
) -> list[tuple[Equipment, EquipmentStateLatest]]:
    stmt = (
        select(Equipment, EquipmentStateLatest)
        .join(EquipmentStateLatest, Equipment.id == EquipmentStateLatest.equipment_id)
        .where(Equipment.factory_id == factory_id)
        .where(Equipment.is_active.is_(True))
        .order_by(Equipment.id)
    )
    if equipment_id is not None:
        stmt = stmt.where(Equipment.id == equipment_id)
    return list(db.execute(stmt).all())


def _next_reading(
    equipment_id: int,
    state: EquipmentStateLatest,
    measured_at: datetime,
    reading_count: int,
) -> SensorReading:
    phase = reading_count + equipment_id * 0.7
    status_bias = {"normal": 0.0, "warn": 0.25, "danger": 0.55}[state.status.value]

    vibration = _clamp(float(state.vibration_rms_g or 0) + sin(phase) * 0.05 + status_bias * 0.02, 0.2, 5.2)
    temperature = _clamp(float(state.hydraulic_temp_c or 0) + sin(phase / 1.7) * 0.35 + status_bias * 0.12, 45.0, 98.0)
    current = _clamp(float(state.motor_current_a or 0) + sin(phase / 1.3) * 0.18 + status_bias * 0.08, 15.0, 36.0)
    pressure = _clamp(float(state.hydraulic_pressure_bar or 0) + sin(phase / 2.1) * 0.7 + status_bias * 0.15, 120.0, 175.0)

    return SensorReading(
        equipment_id=equipment_id,
        measured_at=measured_at,
        vibration_rms_g=_decimal(vibration, 3),
        hydraulic_temp_c=_decimal(temperature, 2),
        motor_current_a=_decimal(current, 2),
        hydraulic_pressure_bar=_decimal(pressure, 2),
        features={"tick": reading_count + 1},
        source="backend_simulator",
    )


def _decimal(value: float, places: int) -> Decimal:
    return Decimal(str(round(value, places)))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
