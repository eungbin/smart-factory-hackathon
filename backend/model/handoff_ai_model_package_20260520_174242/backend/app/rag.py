from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MANUAL_DIR = Path(__file__).resolve().parents[1] / "manuals"


@dataclass(frozen=True)
class ManualChunk:
    id: str
    source: str
    title: str
    content: str


def load_manual_chunks() -> list[ManualChunk]:
    chunks: list[ManualChunk] = []
    for path in sorted(MANUAL_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = path.stem.replace("_", " ")
        sections = re.split(r"\n(?=## )", text)
        for idx, section in enumerate(sections):
            clean = section.strip()
            if not clean:
                continue
            heading = clean.splitlines()[0].lstrip("# ").strip()
            chunks.append(
                ManualChunk(
                    id=f"{path.stem}-{idx}",
                    source=path.name,
                    title=heading or title,
                    content=clean,
                )
            )
    return chunks


def retrieve_manual_chunks(query: str, limit: int = 3) -> list[ManualChunk]:
    query_terms = set(_terms(query))
    scored: list[tuple[int, ManualChunk]] = []
    for chunk in load_manual_chunks():
        haystack_terms = set(_terms(f"{chunk.title} {chunk.content}"))
        overlap = len(query_terms & haystack_terms)
        if overlap:
            scored.append((overlap, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return load_manual_chunks()[:limit]
    return [chunk for _, chunk in scored[:limit]]


def _terms(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9가-힣_]+", text.lower())

