"""Ingests a policy document PDF into the policy_knowledge Qdrant collection.

Pipeline: extract_text_from_pdf -> split_into_sections -> embed_texts ->
build_points -> upsert. Each stage is a plain function so it can be tested
and swapped independently (e.g. a different chunker or embedding model
later) without touching the others.
"""

import io
import re
import uuid
from datetime import date

from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from .client import get_client
from .models import COLLECTION_NAME, POLICY_DOCUMENT_TYPES, effective_date_to_ts

DEFAULT_MAX_CHUNK_CHARS = 1000
_HEADING_MAX_LEN = 80
_HEADING_PREFIX_RE = re.compile(r"^(Section|Article|Part)\s+\w+", re.IGNORECASE)

_embedding_model = None


def extract_text_from_pdf(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """Returns [(page_number, page_text)] with 1-indexed page numbers."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return [(index, page.extract_text() or "") for index, page in enumerate(reader.pages, start=1)]


def _is_heading(line: str) -> bool:
    if not line or len(line) > _HEADING_MAX_LEN:
        return False
    if line[-1] in ".?!,;:":
        return False
    return line.isupper() or bool(_HEADING_PREFIX_RE.match(line))


def _chunk_page(page_number: int, page_text: str, max_chunk_chars: int) -> list[dict]:
    """Groups a page's lines into chunks.

    Real PDF text extraction doesn't reliably preserve blank-line gaps
    between paragraphs (pypdf reconstructs line breaks from glyph
    position, not document structure), so paragraphs are accumulated from
    consecutive non-heading lines and only split on a blank line or the
    next detected heading -- not on a specific separator pattern.
    """
    chunks: list[dict] = []
    current_heading: str | None = None
    buffer: list[str] = []
    buffer_len = 0
    chunk_index = 0
    paragraph_lines: list[str] = []

    def flush_chunk() -> None:
        nonlocal buffer, buffer_len, chunk_index
        if not buffer:
            return
        chunks.append(
            {
                "page_number": page_number,
                "section_title": current_heading,
                "chunk_index": chunk_index,
                "text": "\n\n".join(buffer).strip(),
            }
        )
        chunk_index += 1
        buffer = []
        buffer_len = 0

    def flush_paragraph() -> None:
        nonlocal paragraph_lines, buffer, buffer_len, chunk_index
        if not paragraph_lines:
            return
        paragraph = " ".join(paragraph_lines).strip()
        paragraph_lines = []
        if not paragraph:
            return

        if buffer and buffer_len + len(paragraph) > max_chunk_chars:
            flush_chunk()

        if len(paragraph) > max_chunk_chars:
            flush_chunk()
            for start in range(0, len(paragraph), max_chunk_chars):
                chunks.append(
                    {
                        "page_number": page_number,
                        "section_title": current_heading,
                        "chunk_index": chunk_index,
                        "text": paragraph[start : start + max_chunk_chars],
                    }
                )
                chunk_index += 1
            return

        buffer.append(paragraph)
        buffer_len += len(paragraph)

    for raw_line in page_text.split("\n"):
        line = raw_line.strip()

        if not line:
            flush_paragraph()
            continue

        if _is_heading(line):
            flush_paragraph()
            flush_chunk()
            current_heading = line
            continue

        paragraph_lines.append(line)

    flush_paragraph()
    flush_chunk()
    return chunks


def split_into_sections(
    pages: list[tuple[int, str]],
    *,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> list[dict]:
    """Splits extracted page text into chunks.

    A chunk never spans pages, so page_number stays unambiguous. The
    nearest preceding heading line (if any) on that page is tracked as
    section_title.
    """
    sections: list[dict] = []
    for page_number, page_text in pages:
        sections.extend(_chunk_page(page_number, page_text, max_chunk_chars))
    return sections


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from fastembed import TextEmbedding

        from .models import EMBEDDING_MODEL_NAME

        _embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    return _embedding_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_embedding_model()
    return [vector.tolist() for vector in model.embed(texts)]


def build_points(
    pdf_bytes: bytes,
    *,
    plan_id: str,
    state: str,
    effective_date: date,
    document_type: str,
    source_document: str,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> list[PointStruct]:
    if document_type not in POLICY_DOCUMENT_TYPES:
        raise ValueError(f"Unknown document_type '{document_type}'. Must be one of {POLICY_DOCUMENT_TYPES}.")

    pages = extract_text_from_pdf(pdf_bytes)
    sections = split_into_sections(pages, max_chunk_chars=max_chunk_chars)
    if not sections:
        return []

    vectors = embed_texts([s["text"] for s in sections])

    effective_date_iso = effective_date.isoformat()
    effective_ts = effective_date_to_ts(effective_date)

    points: list[PointStruct] = []
    for section, vector in zip(sections, vectors, strict=True):
        payload = {
            "plan_id": plan_id,
            "state": state,
            "effective_date": effective_date_iso,
            "effective_date_ts": effective_ts,
            "document_type": document_type,
            "source_document": source_document,
            "page_number": section["page_number"],
            "section_title": section["section_title"],
            "chunk_index": section["chunk_index"],
            "text": section["text"],
        }
        points.append(PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload))

    return points


def ingest_policy_document(
    client: QdrantClient | None,
    pdf_bytes: bytes,
    *,
    plan_id: str,
    state: str,
    effective_date: date,
    document_type: str,
    source_document: str,
    collection_name: str = COLLECTION_NAME,
) -> int:
    """Runs the full ingestion pipeline and upserts into Qdrant.

    Returns the number of chunks written. Pass an existing `client` to
    reuse a connection (e.g. across multiple documents); omit it to get a
    fresh one from `get_client()`.
    """
    client = client or get_client()
    points = build_points(
        pdf_bytes,
        plan_id=plan_id,
        state=state,
        effective_date=effective_date,
        document_type=document_type,
        source_document=source_document,
    )
    if points:
        client.upsert(collection_name=collection_name, points=points)
    return len(points)
