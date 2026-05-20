from pydantic import BaseModel


class SensorHistoryPointOut(BaseModel):
    time: str
    measuredAt: str
    vibration: float
    temperature: float
    current: float
    pressure: float


class RulHistoryPointOut(BaseModel):
    date: str
    measuredAt: str
    rul: int
    upper: int
    lower: int


class MaintenanceHistoryOut(BaseModel):
    id: int
    equipId: int
    date: str
    type: str
    tech: str
    parts: str
    result: str
    duration: int
    note: str
