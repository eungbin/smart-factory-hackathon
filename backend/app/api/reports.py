from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.reports import get_monthly_report


router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.get("/reports/monthly")
def read_monthly_report(
    month: str | None = None,
    factory_id: Annotated[int, Query(alias="factoryId")] = 1,
    db: Session = Depends(get_db),
) -> dict:
    report = get_monthly_report(db, factory_id=factory_id, month=month)
    return {"data": report.model_dump()}
