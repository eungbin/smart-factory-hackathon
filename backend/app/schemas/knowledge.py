from typing import Any

from pydantic import BaseModel, Field


class KnowledgeDocumentIn(BaseModel):
    factoryId: int
    title: str
    documentType: str
    equipmentModelId: int | None = None
    fileName: str | None = None
    fileUri: str | None = None
    sourceLabel: str


class KnowledgeDocumentOut(BaseModel):
    documentId: int
    title: str
    documentType: str
    sourceLabel: str


class KnowledgeDocumentSummaryOut(KnowledgeDocumentOut):
    equipmentModelId: int | None
    fileName: str | None
    fileUri: str | None
    uploadedAt: str


class KnowledgeChunkOut(BaseModel):
    chunkId: int
    chunkNo: int
    heading: str | None
    body: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocumentDetailOut(KnowledgeDocumentSummaryOut):
    chunks: list[KnowledgeChunkOut]


class KnowledgeChunkIn(BaseModel):
    chunkNo: int
    heading: str | None = None
    body: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeChunksIn(BaseModel):
    chunks: list[KnowledgeChunkIn]


class KnowledgeChunksCreatedOut(BaseModel):
    inserted: int


class KnowledgeSearchResultOut(BaseModel):
    chunkId: int
    documentId: int
    title: str
    sourceLabel: str
    heading: str | None
    body: str
    score: float
