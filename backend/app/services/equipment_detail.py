from datetime import datetime, timedelta, timezone
from math import sin

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Equipment, EquipmentStateLatest, MaintenanceRecord, PredictionRun, SensorReading
from app.schemas.equipment_detail import MaintenanceHistoryOut, RulHistoryPointOut, SensorHistoryPointOut
from app.services.equipment import get_equipment


KST = timezone(timedelta(hours=9))
BASE_TIME = datetime(2026, 5, 19, 8, 0, tzinfo=KST)


def list_sensor_history(db: Session, equipment_id: int, hours: int = 24) -> list[SensorHistoryPointOut] | None:
    equipment = get_equipment(db, equipment_id)
    if equipment is None:
        return None

    readings = db.execute(
        select(SensorReading)
        .where(SensorReading.equipment_id == equipment_id)
        .order_by(SensorReading.measured_at.desc())
        .limit(hours + 1)
    ).scalars()
    reading_points = list(reversed(list(readings)))
    if reading_points:
        points: list[SensorHistoryPointOut] = []
        for reading in reading_points:
            measured_at = _as_kst(reading.measured_at)
            points.append(
                SensorHistoryPointOut(
                    time=measured_at.strftime("%H:%M"),
                    measuredAt=measured_at.isoformat(),
                    vibration=round(float(reading.vibration_rms_g), 2),
                    temperature=round(float(reading.hydraulic_temp_c), 1),
                    current=round(float(reading.motor_current_a), 1),
                    pressure=round(float(reading.hydraulic_pressure_bar), 1),
                )
            )
        return points

    trending = equipment.status != "normal"
    points: list[SensorHistoryPointOut] = []
    for offset in range(hours, -1, -1):
        measured_at = BASE_TIME - timedelta(hours=offset)
        progress = (hours - offset) / max(hours, 1)
        wave = sin(progress * 3.14159 * 2) * 0.08
        trend = progress if trending else 0
        points.append(
            SensorHistoryPointOut(
                time=measured_at.strftime("%H:%M"),
                measuredAt=measured_at.isoformat(),
                vibration=round(equipment.sensors.vibration + trend * 1.2 + wave, 2),
                temperature=round(equipment.sensors.temp + trend * 5.5 + wave * 8, 1),
                current=round(equipment.sensors.current + trend * 2.4 + wave * 2, 1),
                pressure=round(equipment.sensors.pressure + trend * 8.0 + wave * 5, 1),
            )
        )
    return points


def list_rul_history(db: Session, equipment_id: int, days: int = 30) -> list[RulHistoryPointOut] | None:
    equipment = get_equipment(db, equipment_id)
    if equipment is None:
        return None

    runs = db.execute(
        select(PredictionRun)
        .where(PredictionRun.equipment_id == equipment_id)
        .order_by(PredictionRun.created_at.desc(), PredictionRun.id.desc())
        .limit(days + 1)
    ).scalars()
    run_points = list(reversed(list(runs)))
    if run_points:
        points: list[RulHistoryPointOut] = []
        for run in run_points:
            measured_at = _as_kst(run.created_at)
            points.append(
                RulHistoryPointOut(
                    date=f"{measured_at.month}/{measured_at.day}",
                    measuredAt=measured_at.isoformat(),
                    rul=run.rul_hours,
                    upper=run.rul_upper_hours,
                    lower=run.rul_lower_hours,
                )
            )
        return points

    points: list[RulHistoryPointOut] = []
    for offset in range(days, -1, -1):
        measured_at = BASE_TIME - timedelta(days=offset)
        rul = equipment.rul + offset * 9
        points.append(
            RulHistoryPointOut(
                date=f"{measured_at.month}/{measured_at.day}",
                measuredAt=measured_at.isoformat(),
                rul=rul,
                upper=rul + 24,
                lower=max(0, rul - 24),
            )
        )
    return points


def list_maintenance_history(db: Session, equipment_id: int) -> list[MaintenanceHistoryOut] | None:
    exists = db.execute(select(Equipment.id).where(Equipment.id == equipment_id).where(Equipment.is_active.is_(True))).first()
    if exists is None:
        return None

    records = db.execute(
        select(MaintenanceRecord)
        .where(MaintenanceRecord.equipment_id == equipment_id)
        .order_by(MaintenanceRecord.performed_at.desc(), MaintenanceRecord.id.desc())
    ).scalars()

    return [
        MaintenanceHistoryOut(
            id=record.id,
            equipId=record.equipment_id,
            date=record.performed_at.date().isoformat(),
            type=record.maintenance_type,
            tech=record.technician_name,
            parts=record.parts_text or "없음",
            result=record.result,
            duration=record.duration_minutes,
            note=record.note or "",
        )
        for record in records
    ]


def _as_kst(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(KST)
