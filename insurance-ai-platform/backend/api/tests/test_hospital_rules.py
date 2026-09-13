"""Hospital-scoped rules: the compliance-approval gate, and that an
activated rule actually changes claim resolution through the real
pipeline (not just in isolated graph tests).
"""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

CONDITION = {
    "all": [
        {"field": "has_documents", "op": "eq", "value": True},
        {"field": "out_of_network", "op": "eq", "value": False},
        {"field": "billed_amount", "op": "lte", "value": 2000},
    ]
}


async def _create_draft_rule(client, seed, engineer_id):
    response = await client.post(
        "/rules",
        json={
            "rule_code": "CGH-HIGHER-AUTO-APPROVE",
            "rule_name": "City General higher auto-approve threshold",
            "rule_type": "auto_approval",
            "provider_id": seed.provider_id,
            "rule_definition": {
                "condition": CONDITION,
                "action": "auto_approve",
                "reason": "City General contract allows auto-approval up to $2000.",
            },
            "priority": 50,
            "created_by": engineer_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_rule_cannot_activate_without_any_approval(client, seed):
    engineer_id = seed.engineer_id
    rule = await _create_draft_rule(client, seed, engineer_id)
    await client.post(f"/rules/{rule['rule_id']}/versions/{rule['version']}/submit", params={"submitted_by": engineer_id})

    response = await client.post(
        f"/rules/{rule['rule_id']}/versions/{rule['version']}/activate", json={"activated_by": engineer_id}
    )
    assert response.status_code == 403


async def test_non_compliance_user_cannot_record_an_approval(client, seed):
    engineer_id = seed.engineer_id
    rule = await _create_draft_rule(client, seed, engineer_id)
    await client.post(f"/rules/{rule['rule_id']}/versions/{rule['version']}/submit", params={"submitted_by": engineer_id})

    response = await client.post(
        f"/rules/{rule['rule_id']}/versions/{rule['version']}/approvals",
        json={"approver_id": engineer_id, "approval_status": "approved"},
    )
    assert response.status_code == 403


async def test_rule_activates_after_genuine_compliance_approval(client, seed):
    engineer_id = seed.engineer_id
    rule = await _create_draft_rule(client, seed, engineer_id)
    await client.post(f"/rules/{rule['rule_id']}/versions/{rule['version']}/submit", params={"submitted_by": engineer_id})

    approval = await client.post(
        f"/rules/{rule['rule_id']}/versions/{rule['version']}/approvals",
        json={"approver_id": seed.compliance_id, "approval_status": "approved"},
    )
    assert approval.status_code == 201

    activation = await client.post(
        f"/rules/{rule['rule_id']}/versions/{rule['version']}/activate", json={"activated_by": engineer_id}
    )
    assert activation.status_code == 200
    assert activation.json()["status"] == "active"
    assert activation.json()["approved_by"] == seed.compliance_id


async def test_activating_a_new_version_deprecates_the_previous_active_one(client, seed):
    engineer_id = seed.engineer_id
    v1 = await _create_draft_rule(client, seed, engineer_id)
    await client.post(f"/rules/{v1['rule_id']}/versions/1/submit", params={"submitted_by": engineer_id})
    await client.post(
        f"/rules/{v1['rule_id']}/versions/1/approvals",
        json={"approver_id": seed.compliance_id, "approval_status": "approved"},
    )
    await client.post(f"/rules/{v1['rule_id']}/versions/1/activate", json={"activated_by": engineer_id})

    v2 = await _create_draft_rule(client, seed, engineer_id)
    assert v2["version"] == 2
    await client.post(f"/rules/{v2['rule_id']}/versions/2/submit", params={"submitted_by": engineer_id})
    await client.post(
        f"/rules/{v2['rule_id']}/versions/2/approvals",
        json={"approver_id": seed.compliance_id, "approval_status": "approved"},
    )
    await client.post(f"/rules/{v2['rule_id']}/versions/2/activate", json={"activated_by": engineer_id})

    rules = (await client.get("/rules", params={"provider_id": seed.provider_id})).json()
    by_version = {r["version"]: r["status"] for r in rules}
    assert by_version[1] == "deprecated"
    assert by_version[2] == "active"


async def _activate_hospital_rule(client, seed, engineer_id):
    rule = await _create_draft_rule(client, seed, engineer_id)
    await client.post(f"/rules/{rule['rule_id']}/versions/{rule['version']}/submit", params={"submitted_by": engineer_id})
    await client.post(
        f"/rules/{rule['rule_id']}/versions/{rule['version']}/approvals",
        json={"approver_id": seed.compliance_id, "approval_status": "approved"},
    )
    await client.post(
        f"/rules/{rule['rule_id']}/versions/{rule['version']}/activate", json={"activated_by": engineer_id}
    )
    return rule


async def test_active_hospital_rule_changes_claim_resolution(client, seed):
    engineer_id = seed.engineer_id
    rule = await _activate_hospital_rule(client, seed, engineer_id)

    # $1500: above the global $500 auto-approve threshold (would escalate
    # under global rules alone), but within this hospital's $2000 limit.
    created = (
        await client.post(
            "/claims",
            json={
                "member_id": seed.member_id,
                "policy_id": seed.policy_id,
                "provider_id": seed.provider_id,
                "claim_type": "medical",
                "date_of_service": "2026-08-01",
                "billed_amount": "1500.00",
                "procedure_codes": ["99214"],
            },
        )
    ).json()
    await client.post(
        f"/claims/{created['claim_id']}/documents",
        data={"document_type": "invoice"},
        files={"file": ("invoice.txt", b"invoice", "text/plain")},
    )
    await client.post(f"/claims/{created['claim_id']}/submit")

    recommendation = (await client.get(f"/claims/{created['claim_id']}/recommendation")).json()
    assert recommendation["recommendation_type"] == "approve"
    assert rule["rule_code"] in recommendation["reasoning"]

    timeline = (await client.get(f"/claims/{created['claim_id']}/timeline")).json()
    rules_resolved_event = next(e for e in timeline if e["event_type"] == "rules_resolved")
    assert rules_resolved_event["new_value"]["winning_rule_source"] == "hospital"
    assert rules_resolved_event["new_value"]["winning_rule_id"] == rule["rule_id"]

    # Claim type "medical" is still not in the guardrails' auto-eligible
    # allowlist, so it must still land with a human despite the AI's
    # (hospital-rule-driven) approve recommendation -- the two safety
    # layers are independent.
    final = (await client.get(f"/claims/{created['claim_id']}")).json()
    assert final["status"] == "pending_adjuster_review"


async def test_a_different_hospital_does_not_get_this_rule(client, seed):
    engineer_id = seed.engineer_id
    await _activate_hospital_rule(client, seed, engineer_id)

    created = (
        await client.post(
            "/claims",
            json={
                "member_id": seed.member_id,
                "policy_id": seed.policy_id,
                # No provider_id -- this claim isn't at City General, so
                # the hospital rule must not apply.
                "claim_type": "medical",
                "date_of_service": "2026-08-01",
                "billed_amount": "1500.00",
                "procedure_codes": ["99214"],
            },
        )
    ).json()
    await client.post(
        f"/claims/{created['claim_id']}/documents",
        data={"document_type": "invoice"},
        files={"file": ("invoice.txt", b"invoice", "text/plain")},
    )
    await client.post(f"/claims/{created['claim_id']}/submit")

    recommendation = (await client.get(f"/claims/{created['claim_id']}/recommendation")).json()
    assert recommendation["recommendation_type"] != "approve"
