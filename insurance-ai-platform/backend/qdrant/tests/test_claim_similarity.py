import uuid

from qdrant.claim_similarity import ensure_collection, find_similar_claims, index_claim
from qdrant.client import get_client
from qdrant.ingestion import embed_texts


def _new_id() -> str:
    return str(uuid.uuid4())


def test_finds_the_claim_with_the_closest_content():
    client = get_client()
    ensure_collection(client)

    dental_id = _new_id()
    vision_id = _new_id()
    index_claim(
        client,
        embed=embed_texts,
        claim_id=dental_id,
        claim_number="CLM-0001",
        claim_type="dental",
        procedure_codes=["D1110"],
        diagnosis_codes=[],
        billed_amount="100.00",
        provider_id=None,
        final_decision="approved",
    )
    index_claim(
        client,
        embed=embed_texts,
        claim_id=vision_id,
        claim_number="CLM-0002",
        claim_type="vision",
        procedure_codes=["92014"],
        diagnosis_codes=[],
        billed_amount="80.00",
        provider_id=None,
        final_decision="denied",
    )

    matches = find_similar_claims(
        client,
        embed=embed_texts,
        claim_type="dental",
        procedure_codes=["D1110"],
        diagnosis_codes=[],
        billed_amount="105.00",
        provider_id=None,
        top_k=1,
    )

    assert len(matches) == 1
    assert matches[0]["claim_id"] == dental_id
    assert matches[0]["claim_number"] == "CLM-0001"
    assert matches[0]["final_decision"] == "approved"


def test_excludes_the_given_claim_id():
    client = get_client()
    ensure_collection(client)

    claim_id = _new_id()
    index_claim(
        client,
        embed=embed_texts,
        claim_id=claim_id,
        claim_number="CLM-0003",
        claim_type="dental",
        procedure_codes=["D1110"],
        diagnosis_codes=[],
        billed_amount="100.00",
        provider_id=None,
        final_decision="approved",
    )

    matches = find_similar_claims(
        client,
        embed=embed_texts,
        claim_type="dental",
        procedure_codes=["D1110"],
        diagnosis_codes=[],
        billed_amount="100.00",
        provider_id=None,
        exclude_claim_id=claim_id,
        top_k=5,
    )

    assert all(m["claim_id"] != claim_id for m in matches)


def test_reindexing_the_same_claim_id_replaces_rather_than_duplicates():
    client = get_client()
    ensure_collection(client)

    claim_id = _new_id()
    for decision in ("pending", "approved"):
        index_claim(
            client,
            embed=embed_texts,
            claim_id=claim_id,
            claim_number="CLM-0004",
            claim_type="dental",
            procedure_codes=["D1110"],
            diagnosis_codes=[],
            billed_amount="100.00",
            provider_id=None,
            final_decision=decision,
        )

    matches = find_similar_claims(
        client,
        embed=embed_texts,
        claim_type="dental",
        procedure_codes=["D1110"],
        diagnosis_codes=[],
        billed_amount="100.00",
        provider_id=None,
        top_k=10,
    )

    matching = [m for m in matches if m["claim_id"] == claim_id]
    assert len(matching) == 1
    assert matching[0]["final_decision"] == "approved"
