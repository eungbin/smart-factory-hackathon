from pydantic import BaseModel

from app.schemas.predictions import PredictionOut


class SimulationTickIn(BaseModel):
    factoryId: int = 1
    equipmentId: int | None = None
    windowHours: int = 24


class SimulationTickOut(BaseModel):
    insertedReadings: int
    predictions: list[PredictionOut]
