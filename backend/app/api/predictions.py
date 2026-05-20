from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.predictions import PredictionRunIn
from app.services.predictions import create_prediction_run, get_latest_prediction


router = APIRouter(prefix="/api/v1", tags=["predictions"])


@router.post("/predictions/run")
def run_prediction(payload: PredictionRunIn, db: Session = Depends(get_db)) -> dict:
    prediction = create_prediction_run(db, payload.equipmentId, window_hours=payload.windowHours)
    if prediction is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "equipment_not_found"}})
    return {"data": prediction.model_dump()}


@router.get("/equipment/{equipment_id}/predictions/latest")
def read_latest_prediction(equipment_id: int, db: Session = Depends(get_db)) -> dict:
    prediction = get_latest_prediction(db, equipment_id)
    if prediction is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "prediction_not_found"}})
    return {"data": prediction.model_dump()}
