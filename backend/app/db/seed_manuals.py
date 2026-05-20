from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import KnowledgeChunk, KnowledgeDocument
from app.db.session import SessionLocal
from app.rag.embeddings import embed_text


BACKEND_ROOT = Path(__file__).resolve().parents[2]
MANUALS_DIR = BACKEND_ROOT / "docs" / "manuals"


def seed_manual_knowledge() -> None:
    with SessionLocal() as session:
        result = seed_manual_knowledge_with_session(session)
        session.commit()
    print(f"Seeded manual knowledge: {result['documents']} documents, {result['chunks']} chunks.")


def seed_manual_knowledge_with_session(session: Session) -> dict[str, int]:
    document_count = 0
    chunk_count = 0

    for item in load_manual_documents():
        document = _get_or_create_document(session, item)
        document_count += 1
        chunk_count += _upsert_chunks(session, document.id, item["chunks"])

    return {"documents": document_count, "chunks": chunk_count}


def load_manual_documents(manuals_dir: Path = MANUALS_DIR) -> list[dict]:
    documents = []
    for path in sorted(manuals_dir.glob("*.md")):
        documents.append(_parse_manual_markdown(path))
    return documents


def _parse_manual_markdown(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    metadata, body_start = _parse_front_matter(lines)
    chunks = _parse_chunks(lines[body_start:])
    return {
        "factory_id": int(metadata["factory_id"]),
        "title": metadata["title"],
        "document_type": metadata.get("document_type", "manual"),
        "equipment_model_id": int(metadata["equipment_model_id"]),
        "file_name": path.name,
        "file_uri": f"docs/manuals/{path.name}",
        "source_label": metadata.get("source_label", metadata["title"]),
        "chunks": chunks,
    }


def _parse_front_matter(lines: list[str]) -> tuple[dict[str, str], int]:
    if not lines or lines[0].strip() != "---":
        raise ValueError("manual markdown must start with front matter")

    metadata = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return metadata, index + 1
        key, value = _parse_key_value(line)
        metadata[key] = value

    raise ValueError("manual markdown front matter is not closed")


def _parse_chunks(lines: list[str]) -> list[dict]:
    chunks = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if not line.startswith("## "):
            raise ValueError("manual chunk must start with a level-2 heading")

        heading = line[3:].strip()
        index += 1
        metadata = {}
        while index < len(lines) and lines[index].strip():
            key, value = _parse_key_value(lines[index])
            metadata[key] = value
            index += 1
        while index < len(lines) and not lines[index].strip():
            index += 1

        body_lines = []
        while index < len(lines) and not lines[index].startswith("## "):
            body_lines.append(lines[index])
            index += 1

        chunks.append(
            {
                "chunk_no": len(chunks) + 1,
                "heading": heading,
                "body": "\n".join(body_lines).strip(),
                "metadata": metadata,
            }
        )

    return chunks


def _parse_key_value(line: str) -> tuple[str, str]:
    key, separator, value = line.partition(":")
    if not separator:
        raise ValueError(f"expected key-value line: {line}")
    return key.strip(), value.strip()


def _get_or_create_document(session: Session, item: dict) -> KnowledgeDocument:
    stmt = select(KnowledgeDocument).where(
        KnowledgeDocument.equipment_model_id == item["equipment_model_id"],
        KnowledgeDocument.source_label == item["source_label"],
    )
    document = session.execute(stmt).scalar_one_or_none()
    if document is None:
        document = KnowledgeDocument(
            factory_id=item["factory_id"],
            title=item["title"],
            document_type=item["document_type"],
            equipment_model_id=item["equipment_model_id"],
            file_name=item["file_name"],
            file_uri=item["file_uri"],
            source_label=item["source_label"],
        )
        session.add(document)
        session.flush()
    else:
        document.title = item["title"]
        document.document_type = item["document_type"]
        document.file_name = item["file_name"]
        document.file_uri = item["file_uri"]

    return document


def _upsert_chunks(session: Session, document_id: int, chunks: list[dict]) -> int:
    count = 0
    for item in chunks:
        stmt = select(KnowledgeChunk).where(
            KnowledgeChunk.document_id == document_id,
            KnowledgeChunk.chunk_no == item["chunk_no"],
        )
        chunk = session.execute(stmt).scalar_one_or_none()
        embedding = embed_text(f"{item['heading']}\n{item['body']}")
        if chunk is None:
            chunk = KnowledgeChunk(
                document_id=document_id,
                chunk_no=item["chunk_no"],
                heading=item["heading"],
                body=item["body"],
                embedding=embedding,
                metadata_=item["metadata"],
            )
            session.add(chunk)
        else:
            chunk.heading = item["heading"]
            chunk.body = item["body"]
            chunk.embedding = embedding
            chunk.metadata_ = item["metadata"]
        count += 1
    return count


if __name__ == "__main__":
    seed_manual_knowledge()
