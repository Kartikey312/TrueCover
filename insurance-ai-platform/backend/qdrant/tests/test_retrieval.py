from datetime import date

from qdrant.client import ensure_collection, get_client
from qdrant.ingestion import ingest_policy_document
from qdrant.retrieval import retrieve_policy_context


def _seed(client, make_pdf, *, plan_id, state, effective_date, text, document_type="policy_certificate", source="doc.pdf"):
    pdf_bytes = make_pdf([text])
    ingest_policy_document(
        client,
        pdf_bytes,
        plan_id=plan_id,
        state=state,
        effective_date=effective_date,
        document_type=document_type,
        source_document=source,
    )


def test_retrieve_returns_chunk_with_citation(make_pdf):
    client = get_client()
    ensure_collection(client)

    _seed(
        client,
        make_pdf,
        plan_id="GOLD-PPO-2026",
        state="CA",
        effective_date=date(2025, 1, 1),
        text="SECTION 4: EXCLUSIONS\n\nCosmetic surgery is not covered under this plan.",
    )

    results = retrieve_policy_context(
        client,
        "is cosmetic surgery covered",
        plan_id="GOLD-PPO-2026",
        state="CA",
        as_of=date(2026, 1, 1),
        top_k=3,
    )

    assert len(results) == 1
    chunk = results[0]
    assert "cosmetic surgery" in chunk["text"].lower()
    assert chunk["citation"]["source_document"] == "doc.pdf"
    assert chunk["citation"]["page_number"] == 1
    assert chunk["citation"]["plan_id"] == "GOLD-PPO-2026"
    assert chunk["citation"]["state"] == "CA"
    assert chunk["citation"]["document_type"] == "policy_certificate"
    assert chunk["citation"]["section_title"] == "SECTION 4: EXCLUSIONS"


def test_retrieve_excludes_other_plans_and_states(make_pdf):
    client = get_client()
    ensure_collection(client)

    _seed(
        client, make_pdf, plan_id="GOLD-PPO-2026", state="CA", effective_date=date(2025, 1, 1),
        text="Covers annual checkups.", source="ca_doc.pdf",
    )
    _seed(
        client, make_pdf, plan_id="SILVER-HMO-2026", state="CA", effective_date=date(2025, 1, 1),
        text="Covers annual checkups too.", source="other_plan_doc.pdf",
    )
    _seed(
        client, make_pdf, plan_id="GOLD-PPO-2026", state="NY", effective_date=date(2025, 1, 1),
        text="Covers annual checkups in NY.", source="ny_doc.pdf",
    )

    results = retrieve_policy_context(
        client, "annual checkups", plan_id="GOLD-PPO-2026", state="CA", as_of=date(2026, 1, 1), top_k=10
    )

    assert len(results) == 1
    assert results[0]["citation"]["source_document"] == "ca_doc.pdf"


def test_retrieve_excludes_documents_effective_in_the_future(make_pdf):
    client = get_client()
    ensure_collection(client)

    _seed(
        client, make_pdf, plan_id="GOLD-PPO-2026", state="CA", effective_date=date(2025, 1, 1),
        text="Current terms: covers annual checkups.", source="current.pdf",
    )
    _seed(
        client, make_pdf, plan_id="GOLD-PPO-2026", state="CA", effective_date=date(2027, 1, 1),
        text="Future terms: covers annual checkups plus dental.", source="future.pdf",
    )

    results = retrieve_policy_context(
        client, "annual checkups", plan_id="GOLD-PPO-2026", state="CA", as_of=date(2026, 6, 1), top_k=10
    )

    assert len(results) == 1
    assert results[0]["citation"]["source_document"] == "current.pdf"


def test_retrieve_returns_empty_list_when_nothing_matches(make_pdf):
    client = get_client()
    ensure_collection(client)

    _seed(
        client, make_pdf, plan_id="GOLD-PPO-2026", state="CA", effective_date=date(2025, 1, 1),
        text="Covers annual checkups.",
    )

    results = retrieve_policy_context(
        client, "annual checkups", plan_id="DOES-NOT-EXIST", state="CA", as_of=date(2026, 1, 1)
    )

    assert results == []
