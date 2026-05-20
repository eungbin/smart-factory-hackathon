from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.work_orders import WorkOrderGenerateIn
from app.services.work_orders import generate_work_order


router = APIRouter(prefix="/api/v1", tags=["work-orders"])


@router.post("/work-orders/generate")
def create_work_order(payload: WorkOrderGenerateIn, db: Session = Depends(get_db)) -> dict:
    order = generate_work_order(db, payload.equipmentId, payload.predictionRunId)
    if order is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "equipment_not_found", "message": "설비를 찾을 수 없습니다.", "details": {}}},
        )
    return {"data": order.model_dump()}
