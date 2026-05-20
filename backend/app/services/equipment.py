from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Equipment,
    EquipmentModel,
    EquipmentStateLatest,
    EquipmentStatus,
    FaultTypeCode,
    PredictionFaultProbability,
)
from app.schemas.equipment import EquipmentOut, FaultCandidateOut, SensorsOut


FAULT_TYPE_LABELS = {
    FaultTypeCode.normal: "정상",
    FaultTypeCode.bearing_fault: "베어링 불량",
    FaultTypeCode.belt_loose: "벨트 느슨함",
    FaultTypeCode.rotor_unbalance: "회전체 불평형",
    FaultTypeCode.shaft_misalignment: "축정렬 불량",
    FaultTypeCode.hydraulic_seal: "유압 씰 이상",
    FaultTypeCode.other: "기타",
}


def list_equipment(
    db: Session,
    factory_id: int = 1,
    status: str | None = None,
    include_inactive: bool = False,
) -> list[EquipmentOut]:
    stmt = (
        select(Equipment, EquipmentModel, EquipmentStateLatest)
        .join(EquipmentModel, Equipment.model_id == EquipmentModel.id)
        .join(EquipmentStateLatest, Equipment.id == EquipmentStateLatest.equipment_id)
        .where(Equipment.factory_id == factory_id)
        .order_by(Equipment.id)
    )

    if not include_inactive:
        stmt = stmt.where(Equipment.is_active.is_(True))

    if status is not None:
        stmt = stmt.where(EquipmentStateLatest.status == EquipmentStatus(status))

    rows = db.execute(stmt).all()
    return [to_equipment_out(db, equipment, model, state) for equipment, model, state in rows]


def get_equipment(db: Session, equipment_id: int) -> EquipmentOut | None:
    stmt = (
        select(Equipment, EquipmentModel, EquipmentStateLatest)
        .join(EquipmentModel, Equipment.model_id == EquipmentModel.id)
        .join(EquipmentStateLatest, Equipment.id == EquipmentStateLatest.equipment_id)
        .where(Equipment.id == equipment_id)
        .where(Equipment.is_active.is_(True))
    )
    row = db.execute(stmt).first()
    if row is None:
        return None

    equipment, model, state = row
    return to_equipment_out(db, equipment, model, state)


def to_equipment_out(
    db: Session,
    equipment: Equipment,
    model: EquipmentModel,
    state: EquipmentStateLatest,
) -> EquipmentOut:
    fault_type = None
    if state.fault_type_code is not None and state.fault_type_code != FaultTypeCode.normal:
        fault_type = FAULT_TYPE_LABELS.get(state.fault_type_code, state.fault_type_code.value)

    return EquipmentOut(
        id=equipment.id,
        name=equipment.name,
        model=model.model_name,
        year=equipment.installed_year,
        status=state.status.value,
        rul=_int_or_zero(state.rul_hours),
        rulMin=_int_or_zero(state.rul_lower_hours),
        rulMax=_int_or_zero(state.rul_upper_hours),
        risk=_int_or_zero(state.risk_pct),
        lastMaint=state.last_maintenance_at.isoformat() if state.last_maintenance_at else "",
        nextPlan=state.next_plan_text or "",
        sensors=SensorsOut(
            vibration=_float_or_zero(state.vibration_rms_g),
            temp=_float_or_zero(state.hydraulic_temp_c),
            current=_float_or_zero(state.motor_current_a),
            pressure=_float_or_zero(state.hydraulic_pressure_bar),
        ),
        faultType=fault_type,
        faultConf=_int_or_none(state.fault_confidence_pct),
        faultTop3=_fault_top3(db, state),
    )


def _int_or_zero(value: int | Decimal | None) -> int:
    if value is None:
        return 0
    return int(round(float(value)))


def _int_or_none(value: int | Decimal | None) -> int | None:
    if value is None:
        return None
    return int(round(float(value)))


def _float_or_zero(value: Decimal | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _fault_top3(db: Session, state: EquipmentStateLatest) -> list[FaultCandidateOut]:
    if state.latest_prediction_run_id is not None:
        probabilities = list(
            db.execute(
                select(PredictionFaultProbability)
                .where(PredictionFaultProbability.prediction_run_id == state.latest_prediction_run_id)
                .order_by(PredictionFaultProbability.probability_pct.desc(), PredictionFaultProbability.id)
            ).scalars()
        )
        candidates = [
            FaultCandidateOut(
                faultTypeCode=item.fault_type_code.value,
                faultType=FAULT_TYPE_LABELS.get(item.fault_type_code, item.fault_type_code.value),
                probability=int(round(float(item.probability_pct))),
            )
            for item in probabilities
            if int(round(float(item.probability_pct))) > 0
        ]
        if state.status != EquipmentStatus.normal:
            non_normal = [item for item in candidates if item.faultTypeCode != FaultTypeCode.normal.value]
            if non_normal:
                return non_normal[:3]
        return candidates[:3]

    if state.fault_type_code is not None and state.fault_type_code != FaultTypeCode.normal:
        return [
            FaultCandidateOut(
                faultTypeCode=state.fault_type_code.value,
                faultType=FAULT_TYPE_LABELS.get(state.fault_type_code, state.fault_type_code.value),
                probability=_int_or_none(state.fault_confidence_pct) or _int_or_zero(state.risk_pct),
            )
        ]

    return []
