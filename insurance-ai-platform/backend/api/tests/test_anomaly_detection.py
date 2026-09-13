"""Statistical outlier detection on billed_amount: a claim wildly outside
the range of previously decided claims of the same type gets flagged for
fraud by the FRAUD-STATISTICAL-OUTLIER rule, through the real API +
graph + Postgres -- not a unit test of the z-score math in isolation.
"""

import uuid

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _create_and_decide(client, seed, *, billed_amount: str, decision: str = "approved"):
    created = (
        await client.post(
            "/claims",
            json={
                "member_id": seed.member_id,
                "policy_id": seed.policy_id,
                "provider_id": seed.provider_id,
                "claim_type": "vision",
                "date_of_service": "2026-08-01",
                "billed_amount": billed_amount,
                "procedure_codes": ["92014"],
            },
        )
    ).json()
    await client.post(
        f"/claims/{created['claim_id']}/documents",
        data={"document_type": "invoice"},
        files={"file": ("invoice.txt", b"invoice", "text/plain")},
    )
    submitted = (await client.post(f"/claims/{created['claim_id']}/submit")).json()

    if submitted["final_decision"] == "pending":
        await client.post(
            f"/claims/{submitted['claim_id']}/decision",
            headers=seed.adjuster_headers,
            json={
                "final_decision": decision,
                "approved_amount": billed_amount if decision == "approved" else None,
                "reason": "Reviewed.",
                "idempotency_key": str(uuid.uuid4()),
            },
        )
    return submitted


async def test_claim_far_outside_historical_range_is_flagged_for_fraud(client, seed):
    # Five decided vision claims clustered around $80 establish a
    # baseline low enough in variance that $50,000 is an unmistakable
    # outlier, not a borderline judgment call.
    for amount in ("78.00", "80.00", "82.00", "79.00", "81.00"):
        await _create_and_decide(client, seed, billed_amount=amount)

    outlier = await _create_and_decide(client, seed, billed_amount="50000.00", decision="denied")

    recommendation = (await client.get(f"/claims/{outlier['claim_id']}/recommendation")).json()
    assert recommendation["recommendation_type"] == "flag_for_fraud"

    review = (await client.get(f"/claims/{outlier['claim_id']}/review")).json()
    outlier_rule = next(
        (r for r in review["matched_rules"] if r["rule_code"] == "FRAUD-STATISTICAL-OUTLIER"), None
    )
    assert outlier_rule is not None


async def test_claim_within_historical_range_is_not_flagged(client, seed):
    for amount in ("78.00", "80.00", "82.00", "79.00", "81.00"):
        await _create_and_decide(client, seed, billed_amount=amount)

    typical = await _create_and_decide(client, seed, billed_amount="80.50")

    review = (await client.get(f"/claims/{typical['claim_id']}/review")).json()
    outlier_rule = next(
        (r for r in review["matched_rules"] if r["rule_code"] == "FRAUD-STATISTICAL-OUTLIER"), None
    )
    assert outlier_rule is None


async def test_insufficient_history_never_flags_an_outlier(client, seed):
    # Only two decided claims exist for this type -- nowhere near
    # MIN_SAMPLE_SIZE, so even a wildly different amount must not be
    # flagged: "3 standard deviations from a sample of 2" isn't a
    # real finding.
    await _create_and_decide(client, seed, billed_amount="80.00")
    await _create_and_decide(client, seed, billed_amount="82.00")

    claim = await _create_and_decide(client, seed, billed_amount="50000.00", decision="denied")

    review = (await client.get(f"/claims/{claim['claim_id']}/review")).json()
    outlier_rule = next(
        (r for r in review["matched_rules"] if r["rule_code"] == "FRAUD-STATISTICAL-OUTLIER"), None
    )
    assert outlier_rule is None
