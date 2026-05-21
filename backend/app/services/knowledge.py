from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import KnowledgeChunk, KnowledgeDocument
from app.rag.embeddings import EMBEDDING_DIMENSIONS, embed_text
from app.schemas.knowledge import (
    KnowledgeChunkIn,
    KnowledgeChunkOut,
    KnowledgeChunksCreatedOut,
    KnowledgeDocumentDetailOut,
    KnowledgeDocumentIn,
    KnowledgeDocumentOut,
    KnowledgeDocumentSummaryOut,
    KnowledgeSearchResultOut,
)


def create_document(db: Session, payload: KnowledgeDocumentIn) -> KnowledgeDocumentOut:
    document = KnowledgeDocument(
        factory_id=payload.factoryId,
        title=payload.title,
        document_type=payload.documentType,
        equipment_model_id=payload.equipmentModelId,
        file_name=payload.fileName,
        file_uri=payload.fileUri,
        source_label=payload.sourceLabel,
    )
    db.add(document)
    db.commit()

    return KnowledgeDocumentOut(
        documentId=document.id,
        title=document.title,
        documentType=document.document_type,
        sourceLabel=document.source_label,
    )


def create_chunks(
    db: Session,
    document_id: int,
    chunks: list[KnowledgeChunkIn],
) -> KnowledgeChunksCreatedOut | None:
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        return None

    for chunk in chunks:
        db.add(
            KnowledgeChunk(
                document_id=document_id,
                chunk_no=chunk.chunkNo,
                heading=chunk.heading,
                body=chunk.body,
                embedding=_chunk_embedding(chunk),
                metadata_=chunk.metadata,
            )
        )

    db.commit()
    return KnowledgeChunksCreatedOut(inserted=len(chunks))


def list_documents(
    db: Session,
    document_type: str | None = None,
) -> list[KnowledgeDocumentSummaryOut]:
    stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.uploaded_at.desc(), KnowledgeDocument.id.desc())
    if document_type is not None:
        stmt = stmt.where(KnowledgeDocument.document_type == document_type)

    return [_document_summary(document) for document in db.execute(stmt).scalars().all()]


def get_document(db: Session, document_id: int) -> KnowledgeDocumentDetailOut | None:
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        return None

    chunks = db.execute(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.document_id == document_id)
        .order_by(KnowledgeChunk.chunk_no, KnowledgeChunk.id)
    ).scalars().all()

    return KnowledgeDocumentDetailOut(
        **_document_summary(document).model_dump(),
        chunks=[
            KnowledgeChunkOut(
                chunkId=chunk.id,
                chunkNo=chunk.chunk_no,
                heading=chunk.heading,
                body=chunk.body,
                metadata=chunk.metadata_,
            )
            for chunk in chunks
        ],
    )


def search_chunks(
    db: Session,
    query: str,
    equipment_model_id: int | None = None,
    limit: int = 5,
) -> list[KnowledgeSearchResultOut]:
    query_embedding = embed_text(query)
    distance = KnowledgeChunk.embedding.cosine_distance(query_embedding).label("distance")
    stmt = (
        select(KnowledgeChunk, KnowledgeDocument, distance)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .order_by(distance, KnowledgeChunk.id)
        .limit(max(1, min(limit, 20)))
    )

    if equipment_model_id is not None:
        stmt = stmt.where(
            or_(
                KnowledgeDocument.equipment_model_id == equipment_model_id,
                KnowledgeDocument.equipment_model_id.is_(None),
            )
        )

    rows = db.execute(stmt).all()
    return [
        KnowledgeSearchResultOut(
            chunkId=chunk.id,
            documentId=document.id,
            title=document.title,
            sourceLabel=document.source_label,
            heading=chunk.heading,
            body=chunk.body,
            score=_score(distance_value),
        )
        for chunk, document, distance_value in rows
    ]


def _chunk_embedding(chunk: KnowledgeChunkIn) -> list[float]:
    if chunk.embedding is not None:
        if len(chunk.embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(f"embedding must have {EMBEDDING_DIMENSIONS} dimensions")
        return chunk.embedding
    return embed_text(f"{chunk.heading or ''}\n{chunk.body}")


def _score(distance_value: float | None) -> float:
    if distance_value is None:
        return 0.0
    return round(max(0.0, 1.0 - float(distance_value)), 4)


def _document_summary(document: KnowledgeDocument) -> KnowledgeDocumentSummaryOut:
    return KnowledgeDocumentSummaryOut(
        documentId=document.id,
        title=document.title,
        documentType=document.document_type,
        sourceLabel=document.source_label,
        equipmentModelId=document.equipment_model_id,
        fileName=document.file_name,
        fileUri=document.file_uri,
        uploadedAt=document.uploaded_at.strftime("%Y-%m-%d %H:%M") if document.uploaded_at else "",
    )
