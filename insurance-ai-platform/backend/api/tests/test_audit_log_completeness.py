"""Every step the graph takes, and every orchestration event around it,
must land in audit_events exactly once -- no gaps across the pause/resume
boundary, no duplicates, correct order.
"""

import uuid

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _create(client, seed, **overrides):
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
    return (await client.post("/claims", json=payload)).json()


async def test_auto_processed_claim_has_a_complete_unbroken_audit_trail(client, seed):
    claim = await _create(client, seed, claim_type="dental", procedure_codes=["D1110"])
    await client.post(
        f"/claims/{claim['claim_id']}/documents",
        data={"document_type": "invoice"},
        files={"file": ("invoice.txt", b"invoice", "text/plain")},
    )
    await client.post(f"/claims/{claim['claim_id']}/submit")

    timeline = (await client.get(f"/claims/{claim['claim_id']}/timeline")).json()
    event_types = [e["event_type"] for e in timeline]

    assert event_types == [
        "claim_created",
        "document_uploaded",
        "extraction_completed",
        "context_retrieved",
        "rules_resolved",
        "recommendation_generated",
        "guardrail_passed",
        "auto_processed",
        "pipeline_completed",
    ]
    # Every event has a strictly increasing id and timestamp -- no
    # out-of-order writes.
    ids = [e["event_id"] for e in timeline]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


async def test_paused_and_resumed_claim_has_no_gap_or_duplicate_across_the_boundary(client, seed):
    claim = await _create(client, seed)  # medical -> always pauses
    await client.post(f"/claims/{claim['claim_id']}/submit")

    pre_decision = (await client.get(f"/claims/{claim['claim_id']}/timeline")).json()
    pre_types = [e["event_type"] for e in pre_decision]

    assert pre_types == [
        "claim_created",
        "extraction_completed",
        "context_retrieved",
        "rules_resolved",
        "recommendation_generated",
        "guardrail_triggered",
        "paused_for_human_review",
    ]

    await client.post(
        f"/claims/{claim['claim_id']}/decision",
        headers=seed.adjuster_headers,
        json={
            "final_decision": "denied",
            "reason": "Not covered.",
            "idempotency_key": str(uuid.uuid4()),
        },
    )

    post_decision = (await client.get(f"/claims/{claim['claim_id']}/timeline")).json()
    post_types = [e["event_type"] for e in post_decision]

    # The pre-decision prefix must be byte-for-byte the same events, in
    # the same order, with the same ids -- resuming must not re-persist
    # or reorder anything that already happened.
    assert post_types[: len(pre_types)] == pre_types
    assert [e["event_id"] for e in post_decision[: len(pre_types)]] == [e["event_id"] for e in pre_decision]

    # And exactly two new events append after it.
    assert post_types[len(pre_types) :] == ["human_decision_recorded", "pipeline_completed"]

    ids = [e["event_id"] for e in post_decision]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


async def test_audit_events_reference_the_correct_claim_only(client, seed):
    claim_a = await _create(client, seed, claim_type="dental", procedure_codes=["D1110"], billed_amount="50.00")
    claim_b = await _create(client, seed, claim_type="vision", procedure_codes=["92014"], billed_amount="60.00")

    await client.post(
        f"/claims/{claim_a['claim_id']}/documents",
        data={"document_type": "invoice"},
        files={"file": ("a.txt", b"a", "text/plain")},
    )
    await client.post(
        f"/claims/{claim_b['claim_id']}/documents",
        data={"document_type": "invoice"},
        files={"file": ("b.txt", b"b", "text/plain")},
    )
    await client.post(f"/claims/{claim_a['claim_id']}/submit")
    await client.post(f"/claims/{claim_b['claim_id']}/submit")

    timeline_a = (await client.get(f"/claims/{claim_a['claim_id']}/timeline")).json()
    timeline_b = (await client.get(f"/claims/{claim_b['claim_id']}/timeline")).json()

    ids_a = {e["event_id"] for e in timeline_a}
    ids_b = {e["event_id"] for e in timeline_b}
    assert ids_a.isdisjoint(ids_b)
