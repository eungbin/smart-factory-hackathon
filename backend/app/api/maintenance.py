from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.maintenance import MaintenanceRecordIn
from app.services.maintenance import create_maintenance_record as save_maintenance_record


router = APIRouter(prefix="/api/v1", tags=["maintenance"])


@router.post("/maintenance-records", status_code=201)
def create_maintenance_record(payload: MaintenanceRecordIn, db: Session = Depends(get_db)) -> dict:
    record = save_maintenance_record(db, payload)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "equipment_not_found", "message": "설비를 찾을 수 없습니다.", "details": {}}},
        )
    return {"data": record.model_dump()}
