from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.work_orders import WorkOrderGenerateIn
from app.services.work_orders import generate_work_order, get_work_order, list_work_orders


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


@router.get("/work-orders")
def read_work_orders(db: Session = Depends(get_db)) -> dict:
    orders = list_work_orders(db)
    return {
        "data": [order.model_dump() for order in orders],
        "page": {"limit": len(orders), "nextCursor": None},
    }


@router.get("/work-orders/{work_order_id}")
def read_work_order(work_order_id: int, db: Session = Depends(get_db)) -> dict:
    order = get_work_order(db, work_order_id)
    if order is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "work_order_not_found", "message": "작업지시서를 찾을 수 없습니다.", "details": {}}},
        )
    return {"data": order.model_dump()}
