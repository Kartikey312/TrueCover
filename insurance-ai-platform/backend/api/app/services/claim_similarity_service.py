"""Bridges a claim's own content to the Qdrant-backed claim_similarity
collection (backend/qdrant/claim_similarity.py): indexes a claim once it
has a final decision, and finds the closest-content prior claims --
across every member, not just this one -- for the adjuster's "similar
claims" panel and future fraud/anomaly signals.

Same resilience contract as policy_retrieval_service: Qdrant failures are
caught and logged here, never allowed to break claim processing.
"""

import logging
from functools import lru_cache

from qdrant_client import QdrantClient

from app.config import settings

from qdrant.claim_similarity import ensure_collection, find_similar_claims, index_claim
from qdrant.ingestion import embed_texts

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client() -> QdrantClient:
    from qdrant.client import get_client

    client = get_client(url=settings.qdrant_url)
    ensure_collection(client)
    return client


def index_decided_claim(
    *,
    claim_id: str,
    claim_number: str,
    claim_type: str,
    procedure_codes: list[str],
    diagnosis_codes: list[str],
    billed_amount: str | None,
    provider_id: str | None,
    final_decision: str,
) -> None:
    try:
        index_claim(
            _client(),
            embed=embed_texts,
            claim_id=claim_id,
            claim_number=claim_number,
            claim_type=claim_type,
            procedure_codes=procedure_codes,
            diagnosis_codes=diagnosis_codes,
            billed_amount=billed_amount,
            provider_id=provider_id,
            final_decision=final_decision,
        )
    except Exception:
        logger.warning("Indexing claim %s into claim_similarity failed.", claim_id, exc_info=True)


def find_similar_decided_claims(
    *,
    claim_id: str,
    claim_type: str,
    procedure_codes: list[str],
    diagnosis_codes: list[str],
    billed_amount: str | None,
    provider_id: str | None,
    top_k: int = 5,
) -> list[dict]:
    try:
        matches = find_similar_claims(
            _client(),
            embed=embed_texts,
            claim_type=claim_type,
            procedure_codes=procedure_codes,
            diagnosis_codes=diagnosis_codes,
            billed_amount=billed_amount,
            provider_id=provider_id,
            exclude_claim_id=claim_id,
            top_k=top_k,
        )
    except Exception:
        logger.warning("Similar-claim search in Qdrant failed; returning none.", exc_info=True)
        return []

    return [dict(match) for match in matches]
