from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.equipment_detail import list_maintenance_history, list_rul_history, list_sensor_history


router = APIRouter(prefix="/api/v1", tags=["equipment-detail"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": {"code": "equipment_not_found", "message": "설비를 찾을 수 없습니다.", "details": {}}},
    )


@router.get("/equipment/{equipment_id}/sensor-history")
def read_sensor_history(
    equipment_id: int,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
    db: Session = Depends(get_db),
) -> dict:
    items = list_sensor_history(db, equipment_id, hours=hours)
    if items is None:
        raise _not_found()
    return {"data": [item.model_dump() for item in items]}


@router.get("/equipment/{equipment_id}/rul-history")
def read_rul_history(
    equipment_id: int,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    db: Session = Depends(get_db),
) -> dict:
    items = list_rul_history(db, equipment_id, days=days)
    if items is None:
        raise _not_found()
    return {"data": [item.model_dump() for item in items]}


@router.get("/equipment/{equipment_id}/maintenance-history")
def read_maintenance_history(equipment_id: int, db: Session = Depends(get_db)) -> dict:
    items = list_maintenance_history(db, equipment_id)
    if items is None:
        raise _not_found()
    return {"data": [item.model_dump() for item in items]}
