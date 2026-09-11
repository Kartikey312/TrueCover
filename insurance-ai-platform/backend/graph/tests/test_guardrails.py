from graph.guardrails import (
    AUTO_ELIGIBLE_CLAIM_TYPES,
    AUTO_PROCESS_AMOUNT_CAP,
    evaluate_guardrails,
)

CLEAN_EXTRACTED = {
    "claim_type": "dental",
    "billed_amount": "150.00",
    "diagnosis_codes": ["K02.9"],
    "documents": ["doc-1"],
}
CLEAN_RULES: list[dict] = []
CLEAN_CONTEXT: list[dict] = []


def _run(**overrides):
    extracted = {**CLEAN_EXTRACTED, **overrides.pop("extracted", {})}
    return evaluate_guardrails(
        extracted_data=extracted,
        applicable_rules=overrides.pop("applicable_rules", CLEAN_RULES),
        retrieved_context=overrides.pop("retrieved_context", CLEAN_CONTEXT),
        recommendation_type=overrides.pop("recommendation_type", "approve"),
        confidence_score=overrides.pop("confidence_score", 0.9),
    )


def _names(checks, passed: bool) -> set[str]:
    return {c.name for c in checks if c.passed is passed}


def test_clean_dental_claim_passes_every_check():
    checks = _run()
    assert all(c.passed for c in checks)
    assert len(checks) == 8


def test_auto_eligible_claim_types_are_narrow():
    # Locks in the "first release, route almost everything to a human"
    # requirement -- this set must stay small and explicit.
    assert AUTO_ELIGIBLE_CLAIM_TYPES == frozenset({"dental", "vision"})


def test_claim_type_check_fails_for_medical():
    checks = _run(extracted={"claim_type": "medical"})
    assert "claim_type_auto_eligible" in _names(checks, passed=False)


def test_amount_check_fails_at_or_above_cap():
    checks = _run(extracted={"billed_amount": str(AUTO_PROCESS_AMOUNT_CAP)})
    assert "amount_below_cap" in _names(checks, passed=False)


def test_amount_check_passes_just_below_cap():
    checks = _run(extracted={"billed_amount": "299.99"})
    assert "amount_below_cap" in _names(checks, passed=True)


def test_amount_check_fails_when_amount_unparseable():
    checks = _run(extracted={"billed_amount": "not-a-number"})
    assert "amount_below_cap" in _names(checks, passed=False)


def test_confidence_check_fails_below_claim_type_threshold():
    checks = _run(confidence_score=0.6)
    assert "confidence_meets_threshold" in _names(checks, passed=False)


def test_confidence_check_uses_strict_default_for_unlisted_claim_type():
    # "medical" has no entry in MIN_CONFIDENCE_BY_CLAIM_TYPE, so even a
    # reasonably high confidence should not clear the default bar.
    checks = _run(extracted={"claim_type": "medical"}, confidence_score=0.9)
    assert "confidence_meets_threshold" in _names(checks, passed=False)


def test_behavioral_health_diagnosis_code_blocks_processing():
    checks = _run(extracted={"diagnosis_codes": ["F41.1"]})
    assert "not_behavioral_health" in _names(checks, passed=False)


def test_non_behavioral_diagnosis_code_passes():
    checks = _run(extracted={"diagnosis_codes": ["K02.9"]})
    assert "not_behavioral_health" in _names(checks, passed=True)


def test_denial_recommendation_is_always_blocked():
    checks = _run(recommendation_type="deny")
    assert "not_adverse_determination" in _names(checks, passed=False)


def test_escalate_recommendation_is_blocked():
    checks = _run(recommendation_type="escalate")
    assert "not_adverse_determination" in _names(checks, passed=False)


def test_missing_documents_blocks_processing():
    checks = _run(extracted={"documents": []})
    assert "required_documents_present" in _names(checks, passed=False)


def test_matched_fraud_rule_blocks_processing_even_if_not_the_winning_verdict():
    applicable_rules = [
        {"rule_code": "FRAUD-X", "rule_type": "fraud_detection", "matched": True, "action": "flag_fraud", "reason": "x"},
    ]
    checks = _run(applicable_rules=applicable_rules)
    assert "no_fraud_or_policy_conflict" in _names(checks, passed=False)


def test_matched_compliance_rule_blocks_processing():
    applicable_rules = [
        {"rule_code": "COMP-X", "rule_type": "compliance", "matched": True, "action": "require_review", "reason": "x"},
    ]
    checks = _run(applicable_rules=applicable_rules)
    assert "no_fraud_or_policy_conflict" in _names(checks, passed=False)


def test_unmatched_fraud_rule_does_not_block_processing():
    applicable_rules = [
        {"rule_code": "FRAUD-X", "rule_type": "fraud_detection", "matched": False, "action": None, "reason": ""},
    ]
    checks = _run(applicable_rules=applicable_rules)
    assert "no_fraud_or_policy_conflict" in _names(checks, passed=True)


def test_eligibility_rule_match_does_not_block_processing():
    # Eligibility isn't in BLOCKING_RULE_TYPES -- only fraud/compliance are.
    applicable_rules = [
        {"rule_code": "ELG-X", "rule_type": "eligibility", "matched": True, "action": "require_review", "reason": "x"},
    ]
    checks = _run(applicable_rules=applicable_rules)
    assert "no_fraud_or_policy_conflict" in _names(checks, passed=True)


def test_hospital_override_blocks_processing():
    retrieved_context = [{"source": "hospital_rules", "forces_human_review": True}]
    checks = _run(retrieved_context=retrieved_context)
    assert "no_hospital_override" in _names(checks, passed=False)


def test_no_hospital_override_passes_with_ordinary_context():
    retrieved_context = [{"source": "provider_directory", "network_status": "in_network"}]
    checks = _run(retrieved_context=retrieved_context)
    assert "no_hospital_override" in _names(checks, passed=True)


def test_checks_run_to_completion_even_when_several_fail():
    checks = _run(
        extracted={"claim_type": "medical", "billed_amount": "50000.00", "documents": []},
        confidence_score=0.1,
        recommendation_type="deny",
    )
    failed = _names(checks, passed=False)
    assert {
        "claim_type_auto_eligible",
        "amount_below_cap",
        "confidence_meets_threshold",
        "not_adverse_determination",
        "required_documents_present",
    } <= failed
    # All 8 checks still ran and are reported, not short-circuited.
    assert len(checks) == 8
