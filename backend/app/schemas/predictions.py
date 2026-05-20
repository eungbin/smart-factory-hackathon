from typing import Literal

from pydantic import BaseModel


class PredictionRunIn(BaseModel):
    equipmentId: int
    windowHours: int = 24


class FaultProbabilityOut(BaseModel):
    faultTypeCode: str
    faultType: str
    probability: int


class RootSensorOut(BaseModel):
    sensorName: str
    importance: int
    direction: str
    displayText: str


class PredictionOut(BaseModel):
    predictionRunId: int
    equipmentId: int
    status: Literal["normal", "warn", "danger"]
    rul: int
    rulMin: int
    rulMax: int
    risk: int
    faultTypeCode: str | None
    faultType: str | None
    faultConfidence: int | None
    faultProbabilities: list[FaultProbabilityOut]
    rootSensors: list[RootSensorOut]
    createdAt: str
