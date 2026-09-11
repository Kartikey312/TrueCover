"""Retrieves policy_knowledge chunks applicable to a member's active policy.

Every result is a RetrievedChunk: text and its Citation travel together.
There is no lower-level function here that hands back bare chunk text, so
a caller cannot answer from retrieved content while dropping where it came
from.

Filtering is exact-match on plan_id and state, plus an as-of cutoff on
effective_date (documents effective in the future are excluded). This is
a phase-1 simplification: it does not yet dedupe multiple versions of the
same section down to only the most recent one in effect.
"""

from datetime import date

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

from .models import COLLECTION_NAME, Citation, RetrievedChunk, effective_date_to_ts


def _policy_filter(plan_id: str, state: str, as_of: date) -> Filter:
    return Filter(
        must=[
            FieldCondition(key="plan_id", match=MatchValue(value=plan_id)),
            FieldCondition(key="state", match=MatchValue(value=state)),
            FieldCondition(key="effective_date_ts", range=Range(lte=effective_date_to_ts(as_of))),
        ]
    )


def retrieve_policy_context(
    client: QdrantClient,
    query: str,
    *,
    plan_id: str,
    state: str,
    as_of: date | None = None,
    top_k: int = 5,
    collection_name: str = COLLECTION_NAME,
) -> list[RetrievedChunk]:
    """Returns up to `top_k` chunks relevant to `query`, restricted to the
    given plan_id/state and effective on or before `as_of` (defaults to
    today).
    """
    from .ingestion import embed_texts

    as_of = as_of or date.today()
    query_vector = embed_texts([query])[0]

    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=_policy_filter(plan_id, state, as_of),
        limit=top_k,
        with_payload=True,
    )

    chunks: list[RetrievedChunk] = []
    for point in response.points:
        payload = point.payload or {}
        citation: Citation = {
            "source_document": payload.get("source_document", ""),
            "document_type": payload.get("document_type", ""),
            "page_number": payload.get("page_number", 0),
            "section_title": payload.get("section_title"),
            "plan_id": payload.get("plan_id", ""),
            "state": payload.get("state", ""),
            "effective_date": payload.get("effective_date", ""),
        }
        chunks.append(
            RetrievedChunk(
                text=payload.get("text", ""),
                score=point.score,
                citation=citation,
            )
        )

    return chunks
