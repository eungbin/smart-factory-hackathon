from datetime import datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import EquipmentStateLatest, LearningQueue, MaintenanceRecord
from app.schemas.maintenance import MaintenanceRecordCreatedOut, MaintenanceRecordIn
from app.services.equipment import get_equipment


KST = timezone(timedelta(hours=9))


def create_maintenance_record(db: Session, payload: MaintenanceRecordIn) -> MaintenanceRecordCreatedOut | None:
    equipment = get_equipment(db, payload.equipmentId)
    if equipment is None:
        return None

    performed_at = datetime.combine(datetime.fromisoformat(payload.date).date(), time(hour=9), tzinfo=KST)
    record = MaintenanceRecord(
        equipment_id=payload.equipmentId,
        work_order_id=payload.workOrderId,
        performed_at=performed_at,
        technician_name=payload.technicianName,
        maintenance_type=payload.type,
        result=payload.result,
        duration_minutes=payload.duration,
        parts_text=payload.partsReplaced,
        actions=payload.actions,
        actual_fault_type_code=payload.actualFaultTypeCode,
        ai_accuracy_note=payload.aiAccuracyNote,
        note=payload.note,
        next_plan_text=payload.nextPlan,
    )
    db.add(record)
    db.flush()

    queue_key = f"LQ-{record.id:06d}"
    db.add(
        LearningQueue(
            queue_key=queue_key,
            equipment_id=payload.equipmentId,
            maintenance_record_id=record.id,
            status="queued",
            label_payload={
                "actualFaultTypeCode": payload.actualFaultTypeCode,
                "result": payload.result,
                "actions": payload.actions,
            },
        )
    )

    state = db.get(EquipmentStateLatest, payload.equipmentId)
    if state is not None:
        state.last_maintenance_at = performed_at.date()
        if payload.nextPlan:
            state.next_plan_text = payload.nextPlan

    db.commit()
    return MaintenanceRecordCreatedOut(maintenanceRecordId=record.id, learningQueueId=queue_key, saved=True)
