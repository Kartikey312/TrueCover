"""Duplicate adjuster submissions -- a refreshed page or a network retry
resubmitting the same decision must never create a second, conflicting
final decision.
"""

import uuid

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _create_and_submit(client, seed):
    payload = {
        "member_id": seed.member_id,
        "policy_id": seed.policy_id,
        "provider_id": seed.provider_id,
        "claim_type": "medical",
        "date_of_service": "2026-08-01",
        "billed_amount": "100.00",
        "procedure_codes": ["99213"],
    }
    created = (await client.post("/claims", json=payload)).json()
    submitted = await client.post(f"/claims/{created['claim_id']}/submit")
    return submitted.json()


async def test_replaying_the_same_decision_with_the_same_key_returns_the_cached_result(client, seed):
    claim = await _create_and_submit(client, seed)
    key = str(uuid.uuid4())
    payload = {
        "final_decision": "approved",
        "approved_amount": "100.00",
        "reason": "Reviewed manually.",
        "idempotency_key": key,
    }

    first = await client.post(f"/claims/{claim['claim_id']}/decision", json=payload, headers=seed.adjuster_headers)
    assert first.status_code == 200
    assert first.json()["final_decision"] == "approved"

    second = await client.post(f"/claims/{claim['claim_id']}/decision", json=payload, headers=seed.adjuster_headers)
    assert second.status_code == 200
    assert second.json() == first.json()


async def test_same_key_with_a_different_decision_is_rejected(client, seed):
    claim = await _create_and_submit(client, seed)
    key = str(uuid.uuid4())

    first = await client.post(
        f"/claims/{claim['claim_id']}/decision",
        headers=seed.adjuster_headers,
        json={
            "final_decision": "approved",
            "approved_amount": "100.00",
            "reason": "Reviewed manually.",
            "idempotency_key": key,
        },
    )
    assert first.status_code == 200

    conflicting = await client.post(
        f"/claims/{claim['claim_id']}/decision",
        headers=seed.adjuster_headers,
        json={
            "final_decision": "denied",
            "reason": "Changed my mind.",
            "idempotency_key": key,
        },
    )
    assert conflicting.status_code == 409

    # And the original decision must be untouched.
    unchanged = await client.get(f"/claims/{claim['claim_id']}")
    assert unchanged.json()["final_decision"] == "approved"


async def test_a_fresh_key_against_an_already_decided_claim_is_rejected(client, seed):
    claim = await _create_and_submit(client, seed)

    await client.post(
        f"/claims/{claim['claim_id']}/decision",
        headers=seed.adjuster_headers,
        json={
            "final_decision": "approved",
            "approved_amount": "100.00",
            "reason": "First decision.",
            "idempotency_key": str(uuid.uuid4()),
        },
    )

    second_attempt = await client.post(
        f"/claims/{claim['claim_id']}/decision",
        headers=seed.adjuster_headers,
        json={
            "final_decision": "denied",
            "reason": "Second, unrelated attempt.",
            "idempotency_key": str(uuid.uuid4()),  # genuinely new key
        },
    )
    assert second_attempt.status_code == 409


async def test_replayed_decision_does_not_duplicate_audit_events(client, seed):
    claim = await _create_and_submit(client, seed)
    key = str(uuid.uuid4())
    payload = {
        "final_decision": "approved",
        "approved_amount": "100.00",
        "reason": "Reviewed manually.",
        "idempotency_key": key,
    }

    await client.post(f"/claims/{claim['claim_id']}/decision", json=payload, headers=seed.adjuster_headers)
    timeline_after_first = (await client.get(f"/claims/{claim['claim_id']}/timeline")).json()

    await client.post(f"/claims/{claim['claim_id']}/decision", json=payload, headers=seed.adjuster_headers)
    timeline_after_replay = (await client.get(f"/claims/{claim['claim_id']}/timeline")).json()

    assert len(timeline_after_replay) == len(timeline_after_first)
    assert [e["event_id"] for e in timeline_after_replay] == [e["event_id"] for e in timeline_after_first]
