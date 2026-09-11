"""Shared types and constants for the policy_knowledge retrieval pipeline.

A RetrievedChunk always carries its Citation alongside the text -- there is
no function anywhere in this package that returns chunk text without it,
so a caller cannot answer from retrieved text while dropping where it came
from.
"""

from datetime import date, datetime, timezone
from typing import TypedDict

COLLECTION_NAME = "policy_knowledge"
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

POLICY_DOCUMENT_TYPES = (
    "policy_certificate",
    "summary_of_benefits",
    "exclusions",
    "rider",
    "amendment",
    "other",
)


def effective_date_to_ts(effective_date: date) -> int:
    """Epoch seconds for a calendar date, for Qdrant range filtering."""
    return int(
        datetime(effective_date.year, effective_date.month, effective_date.day, tzinfo=timezone.utc).timestamp()
    )


class PolicyDocumentMetadata(TypedDict):
    plan_id: str
    state: str
    effective_date: str  # ISO date, e.g. "2026-01-01"
    document_type: str  # one of POLICY_DOCUMENT_TYPES
    source_document: str  # original filename


class PolicySectionPayload(PolicyDocumentMetadata):
    effective_date_ts: int
    page_number: int
    section_title: str | None
    chunk_index: int
    text: str


class Citation(TypedDict):
    source_document: str
    document_type: str
    page_number: int
    section_title: str | None
    plan_id: str
    state: str
    effective_date: str


class RetrievedChunk(TypedDict):
    text: str
    score: float
    citation: Citation
