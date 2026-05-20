from pydantic import BaseModel, Field


class MaintenanceRecordIn(BaseModel):
    equipmentId: int
    workOrderId: int | None = None
    date: str
    technicianName: str
    type: str
    result: str
    duration: int = Field(ge=5, le=480)
    actions: dict[str, bool] = Field(default_factory=dict)
    partsReplaced: str | None = None
    actualFaultTypeCode: str | None = None
    aiAccuracyNote: str | None = None
    note: str | None = None
    nextPlan: str | None = None


class MaintenanceRecordCreatedOut(BaseModel):
    maintenanceRecordId: int
    learningQueueId: str
    saved: bool
