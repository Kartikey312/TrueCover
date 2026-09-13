"""Login, token verification, and that write endpoints actually enforce
authentication -- not just that the old client-supplied-id tests still
pass with a header bolted on.
"""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_staff_login_succeeds_with_correct_credentials(client, seed):
    response = await client.post("/auth/login", json={"email": "alex@example.com", "password": "test-password-123"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "alex@example.com"
    assert body["user"]["role"] == "adjuster"
    assert "password_hash" not in body["user"]


async def test_staff_login_rejects_wrong_password(client, seed):
    response = await client.post("/auth/login", json={"email": "alex@example.com", "password": "wrong"})
    assert response.status_code == 401


async def test_staff_login_rejects_unknown_email(client, seed):
    response = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "test-password-123"}
    )
    assert response.status_code == 401


async def test_staff_me_returns_the_authenticated_user(client, seed):
    me = await client.get("/auth/me", headers=seed.adjuster_headers)
    assert me.status_code == 200
    assert me.json()["email"] == "alex@example.com"


async def test_staff_me_rejects_missing_token(client, seed):
    response = await client.get("/auth/me")
    assert response.status_code == 401


async def test_staff_me_rejects_garbage_token(client, seed):
    response = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


async def test_member_login_succeeds_with_correct_member_number_and_dob(client, seed):
    response = await client.post(
        "/auth/member-login", json={"member_number": "MBR-0001", "date_of_birth": "1990-01-01"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["member"]["member_number"] == "MBR-0001"


async def test_member_login_rejects_wrong_date_of_birth(client, seed):
    response = await client.post(
        "/auth/member-login", json={"member_number": "MBR-0001", "date_of_birth": "1999-12-31"}
    )
    assert response.status_code == 401


async def test_a_member_token_cannot_be_used_as_a_staff_token(client, seed):
    """The two token kinds are disjoint -- a member logging in must not
    thereby gain access to staff-only endpoints."""
    member_login = await client.post(
        "/auth/member-login", json={"member_number": "MBR-0001", "date_of_birth": "1990-01-01"}
    )
    member_token = member_login.json()["access_token"]

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 401


async def test_decision_endpoint_rejects_unauthenticated_requests(client, seed):
    created = (
        await client.post(
            "/claims",
            json={
                "member_id": seed.member_id,
                "policy_id": seed.policy_id,
                "provider_id": seed.provider_id,
                "claim_type": "medical",
                "date_of_service": "2026-08-01",
                "billed_amount": "100.00",
                "procedure_codes": ["99213"],
            },
        )
    ).json()
    await client.post(f"/claims/{created['claim_id']}/submit")

    response = await client.post(
        f"/claims/{created['claim_id']}/decision",
        json={"final_decision": "approved", "reason": "x", "idempotency_key": "no-auth-test"},
    )
    assert response.status_code == 401


async def test_member_can_list_their_own_claims(client, seed):
    response = await client.get(f"/members/{seed.member_id}/claims", headers=seed.member_headers)
    assert response.status_code == 200


async def test_member_cannot_list_another_members_claims(client, seed):
    response = await client.get(f"/members/{seed.member_id}/claims", headers=seed.other_member_headers)
    assert response.status_code == 403


async def test_member_cannot_list_another_members_policies(client, seed):
    response = await client.get(f"/members/{seed.member_id}/policies", headers=seed.other_member_headers)
    assert response.status_code == 403


async def test_member_endpoints_reject_unauthenticated_requests(client, seed):
    response = await client.get(f"/members/{seed.member_id}/claims")
    assert response.status_code == 401


async def test_rule_creation_rejects_unauthenticated_requests(client, seed):
    response = await client.post(
        "/rules",
        json={
            "rule_code": "NO-AUTH-TEST",
            "rule_name": "Should be rejected",
            "rule_type": "auto_approval",
            "rule_definition": {
                "condition": {"field": "billed_amount", "op": "lte", "value": 100},
                "action": "auto_approve",
                "reason": "test",
            },
        },
    )
    assert response.status_code == 401
