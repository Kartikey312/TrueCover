"""Mandatory human review, adverse determinations, and the review packet
that supports a decision -- through the real API + graph + Postgres.
"""

import uuid

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _create_and_submit(client, seed, *, upload_doc=True, **overrides):
    payload = {
        "member_id": seed.member_id,
        "policy_id": seed.policy_id,
        "provider_id": seed.provider_id,
        "claim_type": "medical",
        "date_of_service": "2026-08-01",
        "billed_amount": "100.00",
        "procedure_codes": ["99213"],
        **overrides,
    }
    created = (await client.post("/claims", json=payload)).json()
    if upload_doc:
        await client.post(
            f"/claims/{created['claim_id']}/documents",
            data={"document_type": "invoice"},
            files={"file": ("invoice.txt", b"invoice", "text/plain")},
        )
    submitted = await client.post(f"/claims/{created['claim_id']}/submit")
    assert submitted.status_code == 200
    return submitted.json()


# --- mandatory human review: several independent reasons a claim must pause ---


async def test_medical_claim_type_requires_human_review(client, seed):
    # Only dental/vision are auto-eligible -- medical always requires a human.
    claim = await _create_and_submit(client, seed, claim_type="medical")
    assert claim["status"] == "pending_adjuster_review"


async def test_behavioral_health_diagnosis_requires_human_review(client, seed):
    claim = await _create_and_submit(
        client, seed, claim_type="dental", procedure_codes=["D1110"], diagnosis_codes=["F41.1"]
    )
    assert claim["status"] == "pending_adjuster_review"


async def test_missing_documents_requires_human_review(client, seed):
    claim = await _create_and_submit(client, seed, claim_type="vision", procedure_codes=["92014"], upload_doc=False)
    assert claim["status"] == "pending_adjuster_review"


async def test_high_value_claim_requires_human_review(client, seed):
    claim = await _create_and_submit(client, seed, billed_amount="15000.00")
    assert claim["status"] == "pending_adjuster_review"


# --- review packet: what the adjuster is shown ---


async def test_review_packet_contains_everything_the_adjuster_needs(client, seed):
    claim = await _create_and_submit(client, seed)

    review = await client.get(f"/claims/{claim['claim_id']}/review")
    assert review.status_code == 200
    packet = review.json()

    assert packet["member_name"] == "Jane Doe"
    assert packet["policy_number"] == "POL-0001"
    assert packet["provider_name"] == "City General Hospital"
    assert packet["recommendation_type"] is not None
    assert packet["confidence_score"] is not None
    assert len(packet["guardrail_checks"]) == 8
    assert any(not check["passed"] for check in packet["guardrail_checks"])
    assert isinstance(packet["policy_citations"], list) and packet["policy_citations"]
    assert isinstance(packet["audit_history"], list) and packet["audit_history"]


# --- adverse determinations: denials/overrides must never be automatic ---


async def test_adjuster_can_approve_despite_ai_escalation_and_it_is_recorded_as_an_override(client, seed):
    # $600 in-network + documented: no global rule matches (above the
    # $500 auto-approve threshold, below the $10,000 high-value-review
    # threshold), so the AI recommends "escalate" with no opinion --
    # confirming the adjuster's approval below is a genuine override, not
    # agreement.
    claim = await _create_and_submit(client, seed, billed_amount="600.00")

    recommendation_before = await client.get(f"/claims/{claim['claim_id']}/recommendation")
    assert recommendation_before.json()["recommendation_type"] == "escalate"

    decision = await client.post(
        f"/claims/{claim['claim_id']}/decision",
        json={
            "decided_by": seed.adjuster_id,
            "final_decision": "approved",
            "approved_amount": "600.00",
            "reason": "Reviewed manually, documentation checks out.",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert decision.status_code == 200
    body = decision.json()
    assert body["status"] == "approved"
    assert body["final_decision"] == "approved"
    assert body["assigned_adjuster_id"] == seed.adjuster_id

    recommendation_after = await client.get(f"/claims/{claim['claim_id']}/recommendation")
    assert recommendation_after.json()["status"] == "overridden"


async def test_adjuster_can_deny_a_claim(client, seed):
    claim = await _create_and_submit(client, seed)

    decision = await client.post(
        f"/claims/{claim['claim_id']}/decision",
        json={
            "decided_by": seed.adjuster_id,
            "final_decision": "denied",
            "reason": "Not a covered service under this plan.",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "denied"
    assert decision.json()["final_decision"] == "denied"


async def test_decision_cannot_be_pending(client, seed):
    claim = await _create_and_submit(client, seed)

    decision = await client.post(
        f"/claims/{claim['claim_id']}/decision",
        json={
            "decided_by": seed.adjuster_id,
            "final_decision": "pending",
            "reason": "x",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    # "pending" is a structurally valid FinalDecisionStatus, so the schema
    # accepts it -- it's rejected as a business rule in the service layer.
    assert decision.status_code == 400


async def test_cannot_decide_a_claim_that_was_never_submitted(client, seed):
    created = (
        await client.post(
            "/claims",
            json={
                "member_id": seed.member_id,
                "policy_id": seed.policy_id,
                "claim_type": "dental",
                "date_of_service": "2026-08-01",
                "billed_amount": "50.00",
                "procedure_codes": ["D1110"],
            },
        )
    ).json()

    decision = await client.post(
        f"/claims/{created['claim_id']}/decision",
        json={
            "decided_by": seed.adjuster_id,
            "final_decision": "approved",
            "reason": "x",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert decision.status_code == 409


# --- request more information ---


async def test_request_more_information_marks_claim_pending_documents(client, seed):
    claim = await _create_and_submit(client, seed)

    response = await client.post(
        f"/claims/{claim['claim_id']}/request-info",
        json={"requested_by": seed.adjuster_id, "message": "Please send an itemized receipt."},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending_documents"
    assert response.json()["final_decision"] == "pending"


async def test_request_more_information_still_allows_a_later_decision(client, seed):
    claim = await _create_and_submit(client, seed)
    await client.post(
        f"/claims/{claim['claim_id']}/request-info",
        json={"requested_by": seed.adjuster_id, "message": "Need more info."},
    )

    decision = await client.post(
        f"/claims/{claim['claim_id']}/decision",
        json={
            "decided_by": seed.adjuster_id,
            "final_decision": "approved",
            "approved_amount": "100.00",
            "reason": "Confirmed by phone.",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert decision.status_code == 200
    assert decision.json()["final_decision"] == "approved"


async def test_request_more_information_rejected_after_final_decision(client, seed):
    claim = await _create_and_submit(client, seed)
    await client.post(
        f"/claims/{claim['claim_id']}/decision",
        json={
            "decided_by": seed.adjuster_id,
            "final_decision": "denied",
            "reason": "Not covered.",
            "idempotency_key": str(uuid.uuid4()),
        },
    )

    response = await client.post(
        f"/claims/{claim['claim_id']}/request-info",
        json={"requested_by": seed.adjuster_id, "message": "Too late."},
    )
    assert response.status_code == 409
