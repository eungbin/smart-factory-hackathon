from typing import Literal

from pydantic import BaseModel

from app.schemas.equipment import EquipmentOut


class DashboardSummaryOut(BaseModel):
    totalEquipment: int
    dangerCount: int
    warnCount: int
    normalCount: int
    monthlyUptimePct: float


class DashboardAlertOut(BaseModel):
    id: int
    equipmentId: int
    equipmentName: str
    level: Literal["warn", "danger"]
    title: str
    rulHours: int
    rulRangeText: str
    riskPct: int
    faultType: str | None


class DashboardOut(BaseModel):
    summary: DashboardSummaryOut
    alerts: list[DashboardAlertOut]
    equipment: list[EquipmentOut]
