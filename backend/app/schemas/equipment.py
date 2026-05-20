from typing import Literal

from pydantic import BaseModel


EquipmentStatus = Literal["normal", "warn", "danger"]


class SensorsOut(BaseModel):
    vibration: float
    temp: float
    current: float
    pressure: float


class FaultCandidateOut(BaseModel):
    faultTypeCode: str
    faultType: str
    probability: int


class EquipmentOut(BaseModel):
    id: int
    name: str
    model: str
    year: int
    status: EquipmentStatus
    rul: int
    rulMin: int
    rulMax: int
    risk: int
    lastMaint: str
    nextPlan: str
    sensors: SensorsOut
    faultType: str | None
    faultConf: int | None
    faultTop3: list[FaultCandidateOut]
