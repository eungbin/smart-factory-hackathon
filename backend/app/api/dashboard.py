from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.dashboard import get_dashboard


router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard")
def read_dashboard(
    factory_id: Annotated[int, Query(alias="factoryId")] = 1,
    db: Session = Depends(get_db),
) -> dict:
    dashboard = get_dashboard(db, factory_id=factory_id)
    return {"data": dashboard.model_dump()}
