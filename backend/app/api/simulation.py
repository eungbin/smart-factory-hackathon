from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.simulation import SimulationTickIn
from app.services.simulation import create_sensor_tick


router = APIRouter(prefix="/api/v1", tags=["simulation"])


@router.post("/simulation/tick")
def run_simulation_tick(payload: SimulationTickIn, db: Session = Depends(get_db)) -> dict:
    result = create_sensor_tick(
        db,
        factory_id=payload.factoryId,
        equipment_id=payload.equipmentId,
        window_hours=payload.windowHours,
    )
    if payload.equipmentId is not None and result.insertedReadings == 0:
        raise HTTPException(status_code=404, detail={"error": {"code": "equipment_not_found"}})
    return {"data": result.model_dump()}
