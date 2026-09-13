"""Create -> upload documents -> submit -> auto-processed. The clean,
happy path exercised end to end through the real API + graph + Postgres.
"""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _create_claim(client, seed, **overrides):
    payload = {
        "member_id": seed.member_id,
        "policy_id": seed.policy_id,
        "provider_id": seed.provider_id,
        "claim_type": "dental",
        "date_of_service": "2026-08-01",
        "billed_amount": "100.00",
        "procedure_codes": ["D1110"],
        **overrides,
    }
    response = await client.post("/claims", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _upload_document(client, claim_id, *, file_name="invoice.txt", content=b"sample invoice"):
    response = await client.post(
        f"/claims/{claim_id}/documents",
        data={"document_type": "invoice"},
        files={"file": (file_name, content, "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_claim_persists_extracted_fields(client, seed):
    claim = await _create_claim(client, seed)

    assert claim["status"] == "submitted"
    assert claim["final_decision"] == "pending"
    assert claim["current_graph_thread_id"] is None
    assert claim["procedure_codes"] == ["D1110"]
    assert claim["claim_number"].startswith("CLM-")


async def test_get_claim_404_for_unknown_id(client):
    response = await client.get("/claims/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_document_upload_list_and_download(client, seed):
    claim = await _create_claim(client, seed)
    document = await _upload_document(client, claim["claim_id"], content=b"line one\nline two")

    listed = await client.get(f"/claims/{claim['claim_id']}/documents")
    assert listed.status_code == 200
    assert [d["document_id"] for d in listed.json()] == [document["document_id"]]

    file_response = await client.get(f"/claims/{claim['claim_id']}/documents/{document['document_id']}/file")
    assert file_response.status_code == 200
    assert file_response.content == b"line one\nline two"
    assert "inline" in file_response.headers["content-disposition"]


async def test_clean_low_value_dental_claim_auto_processes(client, seed):
    claim = await _create_claim(client, seed)
    await _upload_document(client, claim["claim_id"])

    submitted = await client.post(f"/claims/{claim['claim_id']}/submit")
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()

    assert body["status"] == "approved"
    assert body["final_decision"] == "approved"
    assert body["current_graph_thread_id"] is not None

    recommendation = await client.get(f"/claims/{claim['claim_id']}/recommendation")
    assert recommendation.status_code == 200
    assert recommendation.json()["recommendation_type"] == "approve"
    assert recommendation.json()["status"] == "accepted"


async def test_submit_without_documents_still_processes_but_requires_review(client, seed):
    claim = await _create_claim(client, seed)  # no documents uploaded

    submitted = await client.post(f"/claims/{claim['claim_id']}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_adjuster_review"


async def test_double_submit_is_rejected(client, seed):
    claim = await _create_claim(client, seed)
    await _upload_document(client, claim["claim_id"])

    first = await client.post(f"/claims/{claim['claim_id']}/submit")
    assert first.status_code == 200

    second = await client.post(f"/claims/{claim['claim_id']}/submit")
    assert second.status_code == 409
