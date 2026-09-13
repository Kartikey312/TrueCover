"""Vector similarity search over historical claims, for fraud/precedent
context: "what did we decide the last time a claim looked like this one,
regardless of which member filed it."

Separate from policy_knowledge (backend/qdrant/{models,retrieval,ingestion}.py)
-- different collection, different embedding subject (a claim's own
content, not a policy document's text), different lifecycle (a claim is
indexed once it reaches a final decision, not ingested from a document
upload).
"""

from typing import Any, TypedDict

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PayloadSchemaType, PointStruct, VectorParams

COLLECTION_NAME = "claim_similarity"
EMBEDDING_DIM = 384


class ClaimSimilarityPayload(TypedDict):
    claim_id: str
    claim_number: str
    claim_type: str
    billed_amount: str | None
    final_decision: str
    provider_id: str | None


class SimilarClaimMatch(TypedDict):
    claim_id: str
    claim_number: str
    claim_type: str
    billed_amount: str | None
    final_decision: str
    score: float


def ensure_collection(client: QdrantClient, collection_name: str = COLLECTION_NAME) -> None:
    if client.collection_exists(collection_name):
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )
    client.create_payload_index(collection_name, "claim_type", field_schema=PayloadSchemaType.KEYWORD)


def claim_to_text(
    *,
    claim_type: str,
    procedure_codes: list[str],
    diagnosis_codes: list[str],
    billed_amount: str | None,
    provider_id: str | None,
) -> str:
    """A short, deterministic text summary of a claim's clinical/billing
    shape -- embedded and searched on, never shown to a user verbatim.
    """
    parts = [f"{claim_type} claim"]
    if procedure_codes:
        parts.append(f"procedure codes {', '.join(sorted(procedure_codes))}")
    if diagnosis_codes:
        parts.append(f"diagnosis codes {', '.join(sorted(diagnosis_codes))}")
    if billed_amount is not None:
        parts.append(f"billed amount {billed_amount}")
    if provider_id:
        parts.append(f"provider {provider_id}")
    return "; ".join(parts)


def index_claim(
    client: QdrantClient,
    *,
    embed: Any,
    claim_id: str,
    claim_number: str,
    claim_type: str,
    procedure_codes: list[str],
    diagnosis_codes: list[str],
    billed_amount: str | None,
    provider_id: str | None,
    final_decision: str,
    collection_name: str = COLLECTION_NAME,
) -> None:
    """Upserts one claim's vector + payload. `embed` is a callable
    `list[str] -> list[list[float]]` (see qdrant.ingestion.embed_texts) --
    injected rather than imported directly so this module has no hard
    dependency on the fastembed model choice.
    """
    text = claim_to_text(
        claim_type=claim_type,
        procedure_codes=procedure_codes,
        diagnosis_codes=diagnosis_codes,
        billed_amount=billed_amount,
        provider_id=provider_id,
    )
    vector = embed([text])[0]

    payload: ClaimSimilarityPayload = {
        "claim_id": claim_id,
        "claim_number": claim_number,
        "claim_type": claim_type,
        "billed_amount": billed_amount,
        "final_decision": final_decision,
        "provider_id": provider_id,
    }
    # Deterministic point id from claim_id so re-indexing (e.g. a decision
    # changing) replaces the same point rather than duplicating it.
    client.upsert(
        collection_name=collection_name,
        points=[PointStruct(id=claim_id, vector=vector, payload=dict(payload))],
    )


def find_similar_claims(
    client: QdrantClient,
    *,
    embed: Any,
    claim_type: str,
    procedure_codes: list[str],
    diagnosis_codes: list[str],
    billed_amount: str | None,
    provider_id: str | None,
    exclude_claim_id: str | None = None,
    top_k: int = 5,
    collection_name: str = COLLECTION_NAME,
) -> list[SimilarClaimMatch]:
    text = claim_to_text(
        claim_type=claim_type,
        procedure_codes=procedure_codes,
        diagnosis_codes=diagnosis_codes,
        billed_amount=billed_amount,
        provider_id=provider_id,
    )
    vector = embed([text])[0]

    query_filter = None
    if exclude_claim_id:
        # Qdrant filters select what to keep, so "exclude this one" is
        # expressed as must_not rather than a positive match.
        query_filter = Filter(must_not=[FieldCondition(key="claim_id", match=MatchValue(value=exclude_claim_id))])

    response = client.query_points(
        collection_name=collection_name,
        query=vector,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )

    matches: list[SimilarClaimMatch] = []
    for point in response.points:
        payload = point.payload or {}
        matches.append(
            SimilarClaimMatch(
                claim_id=payload.get("claim_id", ""),
                claim_number=payload.get("claim_number", ""),
                claim_type=payload.get("claim_type", ""),
                billed_amount=payload.get("billed_amount"),
                final_decision=payload.get("final_decision", ""),
                score=point.score,
            )
        )
    return matches
