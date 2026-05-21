from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.knowledge import KnowledgeChunksIn, KnowledgeDocumentIn
from app.services.knowledge import create_chunks, create_document, get_document, list_documents, search_chunks


router = APIRouter(prefix="/api/v1", tags=["knowledge"])


@router.post("/knowledge/documents")
def create_knowledge_document(payload: KnowledgeDocumentIn, db: Session = Depends(get_db)) -> dict:
    document = create_document(db, payload)
    return {"data": document.model_dump()}


@router.get("/knowledge/documents")
def list_knowledge_documents(
    documentType: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    documents = list_documents(db, documentType)
    return {"data": [item.model_dump() for item in documents]}


@router.get("/knowledge/documents/{document_id}")
def read_knowledge_document(document_id: int, db: Session = Depends(get_db)) -> dict:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "knowledge_document_not_found", "message": "문서를 찾을 수 없습니다.", "details": {}}},
        )
    return {"data": document.model_dump()}


@router.post("/knowledge/documents/{document_id}/chunks")
def create_knowledge_chunks(document_id: int, payload: KnowledgeChunksIn, db: Session = Depends(get_db)) -> dict:
    chunks = create_chunks(db, document_id, payload.chunks)
    if chunks is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "knowledge_document_not_found", "message": "문서를 찾을 수 없습니다.", "details": {}}},
        )
    return {"data": chunks.model_dump()}


@router.get("/knowledge/search")
def search_knowledge(
    q: str = Query(..., min_length=1),
    equipmentModelId: int | None = None,
    limit: int = 5,
    db: Session = Depends(get_db),
) -> dict:
    results = search_chunks(db, q, equipmentModelId, limit)
    return {"data": [item.model_dump() for item in results]}
