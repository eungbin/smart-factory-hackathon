from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Equipment,
    EquipmentStateLatest,
    FaultTypeCode,
    PredictionFaultProbability,
    PredictionRootCause,
    PredictionRun,
    SensorReading,
)
from app.ml.contracts import SensorPoint, SensorWindow
from app.ml.handoff_runtime import infer
from app.schemas.predictions import FaultProbabilityOut, PredictionOut, RootSensorOut


FAULT_TYPE_LABELS = {
    FaultTypeCode.normal: "정상",
    FaultTypeCode.bearing_fault: "베어링 불량",
    FaultTypeCode.belt_loose: "벨트 장력 이상",
    FaultTypeCode.rotor_unbalance: "회전체 불균형",
    FaultTypeCode.shaft_misalignment: "축정렬 불량",
    FaultTypeCode.hydraulic_seal: "유압 씰 이상",
    FaultTypeCode.other: "기타",
}


def create_prediction_run(
    db: Session,
    equipment_id: int,
    window_hours: int = 24,
    commit: bool = True,
) -> PredictionOut | None:
    state = _get_active_state(db, equipment_id)
    if state is None:
        return None

    sensor_points = _load_sensor_points(db, equipment_id, state, window_hours)
    result = infer(SensorWindow(equipment_id=equipment_id, points=sensor_points))

    prediction_run = PredictionRun(
        equipment_id=equipment_id,
        input_window_start=sensor_points[0].measured_at,
        input_window_end=sensor_points[-1].measured_at,
        input_readings_count=len(sensor_points),
        status=result.status,
        rul_hours=result.rul_hours,
        rul_lower_hours=result.rul_lower_hours,
        rul_upper_hours=result.rul_upper_hours,
        risk_pct=Decimal(str(result.risk_pct)),
        fault_type_code=result.fault_type_code,
        fault_confidence_pct=Decimal(str(result.fault_confidence_pct)) if result.fault_confidence_pct is not None else None,
        summary=result.summary,
        raw_output=result.raw_output,
    )
    db.add(prediction_run)
    db.flush()

    for probability in result.fault_probabilities:
        db.add(
            PredictionFaultProbability(
                prediction_run_id=prediction_run.id,
                fault_type_code=probability.fault_type_code,
                probability_pct=Decimal(str(probability.probability_pct)),
            )
        )

    for index, root_sensor in enumerate(result.root_sensors, start=1):
        db.add(
            PredictionRootCause(
                prediction_run_id=prediction_run.id,
                sensor_name=root_sensor.sensor_name,
                importance_pct=Decimal(str(root_sensor.importance_pct)),
                direction=root_sensor.direction,
                display_text=root_sensor.display_text,
                rank_no=index,
            )
        )

    state.status = result.status
    state.rul_hours = result.rul_hours
    state.rul_lower_hours = result.rul_lower_hours
    state.rul_upper_hours = result.rul_upper_hours
    state.risk_pct = Decimal(str(result.risk_pct))
    state.fault_type_code = result.fault_type_code
    state.fault_confidence_pct = (
        Decimal(str(result.fault_confidence_pct)) if result.fault_confidence_pct is not None else None
    )
    state.latest_prediction_run_id = prediction_run.id
    db.flush()

    if commit:
        db.commit()

    return get_prediction_out(db, prediction_run.id)


def get_latest_prediction(db: Session, equipment_id: int) -> PredictionOut | None:
    stmt = (
        select(PredictionRun.id)
        .where(PredictionRun.equipment_id == equipment_id)
        .order_by(PredictionRun.created_at.desc(), PredictionRun.id.desc())
        .limit(1)
    )
    prediction_run_id = db.execute(stmt).scalar_one_or_none()
    if prediction_run_id is None:
        return None
    return get_prediction_out(db, prediction_run_id)


def get_latest_root_sensor_texts(db: Session, equipment_id: int) -> list[str]:
    latest = get_latest_prediction(db, equipment_id)
    if latest is None:
        return []
    return [sensor.displayText for sensor in latest.rootSensors]


def get_prediction_out(db: Session, prediction_run_id: int) -> PredictionOut:
    prediction_run = db.get(PredictionRun, prediction_run_id)
    probabilities = db.execute(
        select(PredictionFaultProbability)
        .where(PredictionFaultProbability.prediction_run_id == prediction_run_id)
        .order_by(PredictionFaultProbability.probability_pct.desc(), PredictionFaultProbability.id)
    ).scalars()
    root_sensors = db.execute(
        select(PredictionRootCause)
        .where(PredictionRootCause.prediction_run_id == prediction_run_id)
        .order_by(PredictionRootCause.rank_no, PredictionRootCause.id)
    ).scalars()

    return PredictionOut(
        predictionRunId=prediction_run.id,
        equipmentId=prediction_run.equipment_id,
        status=prediction_run.status.value,
        rul=prediction_run.rul_hours,
        rulMin=prediction_run.rul_lower_hours,
        rulMax=prediction_run.rul_upper_hours,
        risk=int(prediction_run.risk_pct),
        faultTypeCode=prediction_run.fault_type_code.value if prediction_run.fault_type_code else None,
        faultType=FAULT_TYPE_LABELS.get(prediction_run.fault_type_code) if prediction_run.fault_type_code else None,
        faultConfidence=int(prediction_run.fault_confidence_pct) if prediction_run.fault_confidence_pct is not None else None,
        faultProbabilities=[
            FaultProbabilityOut(
                faultTypeCode=probability.fault_type_code.value,
                faultType=FAULT_TYPE_LABELS[probability.fault_type_code],
                probability=int(probability.probability_pct),
            )
            for probability in probabilities
        ],
        rootSensors=[
            RootSensorOut(
                sensorName=root_sensor.sensor_name,
                importance=int(root_sensor.importance_pct),
                direction=root_sensor.direction,
                displayText=root_sensor.display_text,
            )
            for root_sensor in root_sensors
        ],
        createdAt=prediction_run.created_at.isoformat(),
    )


def _get_active_state(db: Session, equipment_id: int) -> EquipmentStateLatest | None:
    stmt = (
        select(EquipmentStateLatest)
        .join(Equipment, Equipment.id == EquipmentStateLatest.equipment_id)
        .where(Equipment.id == equipment_id)
        .where(Equipment.is_active.is_(True))
    )
    return db.execute(stmt).scalar_one_or_none()


def _load_sensor_points(
    db: Session,
    equipment_id: int,
    state: EquipmentStateLatest,
    window_hours: int,
) -> list[SensorPoint]:
    end_at = state.latest_sensor_reading_at
    if end_at is None:
        return [_state_to_sensor_point(state)]

    start_at = end_at - timedelta(hours=window_hours)
    readings = db.execute(
        select(SensorReading)
        .where(SensorReading.equipment_id == equipment_id)
        .where(SensorReading.measured_at >= start_at)
        .order_by(SensorReading.measured_at)
    ).scalars()
    points = [_reading_to_sensor_point(reading) for reading in readings]
    return points or [_state_to_sensor_point(state)]


def _reading_to_sensor_point(reading: SensorReading) -> SensorPoint:
    return SensorPoint(
        measured_at=reading.measured_at,
        vibration_rms_g=float(reading.vibration_rms_g),
        hydraulic_temp_c=float(reading.hydraulic_temp_c),
        motor_current_a=float(reading.motor_current_a),
        hydraulic_pressure_bar=float(reading.hydraulic_pressure_bar),
    )


def _state_to_sensor_point(state: EquipmentStateLatest) -> SensorPoint:
    measured_at = state.latest_sensor_reading_at or state.updated_at
    return SensorPoint(
        measured_at=measured_at,
        vibration_rms_g=float(state.vibration_rms_g or 0),
        hydraulic_temp_c=float(state.hydraulic_temp_c or 0),
        motor_current_a=float(state.motor_current_a or 0),
        hydraulic_pressure_bar=float(state.hydraulic_pressure_bar or 0),
    )
