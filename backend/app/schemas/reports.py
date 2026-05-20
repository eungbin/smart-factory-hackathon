from pydantic import BaseModel


class ReportMonthOut(BaseModel):
    month: str
    label: str


class ReportKpisOut(BaseModel):
    unplannedDowntimeHours: int
    preventedCount: int
    mttrMinutes: int
    learningDataCount: int


class MonthlyStatOut(BaseModel):
    month: str
    downtime: int
    prevented: int
    mttr: int


class FaultDistributionOut(BaseModel):
    name: str
    value: int
    color: str


class ReportInsightOut(BaseModel):
    icon: str
    title: str
    body: str
    priority: str


class LearnedKnowledgeOut(BaseModel):
    id: str
    equip: str
    content: str
    confidence: int
    date: str


class MonthlyReportOut(BaseModel):
    month: str
    availableMonths: list[ReportMonthOut]
    kpis: ReportKpisOut
    monthlyStats: list[MonthlyStatOut]
    faultDistribution: list[FaultDistributionOut]
    insights: list[ReportInsightOut]
    learnedKnowledge: list[LearnedKnowledgeOut]
