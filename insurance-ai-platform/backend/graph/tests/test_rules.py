from graph.rules import DEFAULT_RULES, evaluate_rules, resolve_verdict

BASE_EXTRACTED = {
    "claim_type": "medical",
    "billed_amount": "100.00",
    "documents": ["doc-1"],
}

IN_NETWORK_CONTEXT = [{"source": "provider_directory", "network_status": "in_network"}]
OUT_OF_NETWORK_CONTEXT = [{"source": "provider_directory", "network_status": "out_of_network"}]


def test_low_value_in_network_documented_claim_auto_approves():
    results = evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT)
    assert resolve_verdict(results) == "auto_approve"


def test_missing_documents_requires_review():
    extracted = {**BASE_EXTRACTED, "documents": []}
    results = evaluate_rules(extracted, IN_NETWORK_CONTEXT)
    assert resolve_verdict(results) == "require_review"


def test_high_value_claim_requires_review():
    extracted = {**BASE_EXTRACTED, "billed_amount": "15000.00"}
    results = evaluate_rules(extracted, IN_NETWORK_CONTEXT)
    assert resolve_verdict(results) == "require_review"


def test_out_of_network_non_trivial_claim_flags_fraud():
    extracted = {**BASE_EXTRACTED, "billed_amount": "2000.00"}
    results = evaluate_rules(extracted, OUT_OF_NETWORK_CONTEXT)
    assert resolve_verdict(results) == "flag_fraud"


def test_unrecognized_claim_type_auto_denies():
    extracted = {**BASE_EXTRACTED, "claim_type": "not_a_real_type"}
    results = evaluate_rules(extracted, IN_NETWORK_CONTEXT)
    assert resolve_verdict(results) == "auto_deny"


def test_deny_outranks_other_matches():
    # Missing docs (require_review) AND an invalid claim type (auto_deny)
    # both match here -- deny must win the priority ordering.
    extracted = {**BASE_EXTRACTED, "claim_type": "bogus", "documents": []}
    results = evaluate_rules(extracted, IN_NETWORK_CONTEXT)
    assert resolve_verdict(results) == "auto_deny"


def test_no_rules_match_returns_no_match():
    extracted = {**BASE_EXTRACTED, "billed_amount": "2000.00"}  # mid-range, in-network, documented
    results = evaluate_rules(extracted, IN_NETWORK_CONTEXT)
    assert resolve_verdict(results) == "no_match"


def test_evaluate_rules_reports_every_rule():
    results = evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT)
    assert {r["rule_code"] for r in results} == {rule.code for rule in DEFAULT_RULES}


def test_unmatched_rule_has_no_action_or_reason():
    results = evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT)
    unmatched = [r for r in results if not r["matched"]]
    assert unmatched
    for result in unmatched:
        assert result["action"] is None
        assert result["reason"] == ""


def test_resolve_verdict_with_no_results_is_no_match():
    assert resolve_verdict([]) == "no_match"
