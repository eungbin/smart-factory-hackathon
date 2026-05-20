from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.equipment import get_equipment, list_equipment


router = APIRouter(prefix="/api/v1", tags=["equipment"])
EquipmentStatusQuery = Literal["normal", "warn", "danger"]


@router.get("/equipment")
def read_equipment_list(
    factory_id: Annotated[int, Query(alias="factoryId")] = 1,
    status: EquipmentStatusQuery | None = None,
    include_inactive: Annotated[bool, Query(alias="includeInactive")] = False,
    db: Session = Depends(get_db),
) -> dict:
    items = list_equipment(
        db,
        factory_id=factory_id,
        status=status,
        include_inactive=include_inactive,
    )
    return {
        "data": [item.model_dump() for item in items],
        "page": {"limit": len(items), "nextCursor": None},
    }


@router.get("/equipment/{equipment_id}")
def read_equipment(equipment_id: int, db: Session = Depends(get_db)) -> dict:
    item = get_equipment(db, equipment_id)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "equipment_not_found",
                    "message": "설비를 찾을 수 없습니다.",
                    "details": {},
                }
            },
        )

    return {"data": item.model_dump()}
