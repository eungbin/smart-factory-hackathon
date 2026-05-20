from pydantic import BaseModel


class WorkOrderGenerateIn(BaseModel):
    equipmentId: int
    predictionRunId: int | None = None
    recipientUserId: int | None = None


class WorkOrderStepOut(BaseModel):
    no: int
    category: str
    action: str
    tool: str
    time: str
    safety: bool


class WorkOrderPartOut(BaseModel):
    name: str
    qty: str
    stock: str


class WorkOrderOut(BaseModel):
    id: int
    equipId: int
    equipName: str
    generatedAt: str
    rul: str
    risk: int
    faultType: str
    rootSensors: list[str]
    source: str
    status: str
    steps: list[WorkOrderStepOut]
    parts: list[WorkOrderPartOut]
    totalTime: str
    techLevel: str
    caution: str
