from datetime import datetime, timedelta, timezone

from graph.rules import (
    DEFAULT_GLOBAL_RULES,
    Rule,
    evaluate_condition,
    evaluate_rules,
    resolve_verdict,
    rule_from_dict,
)

BASE_EXTRACTED = {
    "claim_type": "medical",
    "billed_amount": "100.00",
    "documents": ["doc-1"],
}

IN_NETWORK_CONTEXT = [{"source": "provider_directory", "network_status": "in_network"}]
OUT_OF_NETWORK_CONTEXT = [{"source": "provider_directory", "network_status": "out_of_network"}]

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


# --- condition DSL -----------------------------------------------------


def test_leaf_condition_compares_field():
    facts = {"billed_amount": 100}
    assert evaluate_condition({"field": "billed_amount", "op": "lte", "value": 500}, facts) is True
    assert evaluate_condition({"field": "billed_amount", "op": "gt", "value": 500}, facts) is False


def test_all_combinator_requires_every_condition():
    facts = {"a": True, "b": False}
    condition = {"all": [{"field": "a", "op": "eq", "value": True}, {"field": "b", "op": "eq", "value": True}]}
    assert evaluate_condition(condition, facts) is False


def test_any_combinator_requires_one_condition():
    facts = {"a": True, "b": False}
    condition = {"any": [{"field": "a", "op": "eq", "value": True}, {"field": "b", "op": "eq", "value": True}]}
    assert evaluate_condition(condition, facts) is True


def test_not_combinator_negates():
    facts = {"a": True}
    assert evaluate_condition({"not": {"field": "a", "op": "eq", "value": True}}, facts) is False


def test_is_empty_and_is_not_empty_ops():
    assert evaluate_condition({"field": "docs", "op": "is_empty", "value": None}, {"docs": []}) is True
    assert evaluate_condition({"field": "docs", "op": "is_not_empty", "value": None}, {"docs": ["x"]}) is True


def test_missing_field_is_treated_as_none_and_fails_comparisons():
    assert evaluate_condition({"field": "nope", "op": "eq", "value": "x"}, {}) is False


# --- default global rules against the standard DSL ----------------------


def test_low_value_in_network_documented_claim_auto_approves():
    results = evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT)
    assert resolve_verdict(results)[0] == "auto_approve"


def test_missing_documents_requires_review():
    extracted = {**BASE_EXTRACTED, "documents": []}
    results = evaluate_rules(extracted, IN_NETWORK_CONTEXT)
    assert resolve_verdict(results)[0] == "require_review"


def test_high_value_claim_requires_review():
    extracted = {**BASE_EXTRACTED, "billed_amount": "15000.00"}
    results = evaluate_rules(extracted, IN_NETWORK_CONTEXT)
    assert resolve_verdict(results)[0] == "require_review"


def test_out_of_network_non_trivial_claim_flags_fraud():
    extracted = {**BASE_EXTRACTED, "billed_amount": "2000.00"}
    results = evaluate_rules(extracted, OUT_OF_NETWORK_CONTEXT)
    assert resolve_verdict(results)[0] == "flag_fraud"


def test_unrecognized_claim_type_auto_denies():
    extracted = {**BASE_EXTRACTED, "claim_type": "not_a_real_type"}
    results = evaluate_rules(extracted, IN_NETWORK_CONTEXT)
    assert resolve_verdict(results)[0] == "auto_deny"


def test_deny_outranks_other_matches_via_priority():
    # Missing docs (priority 60) AND an invalid claim type (priority 100)
    # both match here -- the higher-priority rule must win.
    extracted = {**BASE_EXTRACTED, "claim_type": "bogus", "documents": []}
    results = evaluate_rules(extracted, IN_NETWORK_CONTEXT)
    action, winner = resolve_verdict(results)
    assert action == "auto_deny"
    assert winner["rule_code"] == "ELG-INVALID-CLAIM-TYPE"


def test_no_rules_match_returns_no_match():
    extracted = {**BASE_EXTRACTED, "billed_amount": "2000.00"}  # mid-range, in-network, documented
    results = evaluate_rules(extracted, IN_NETWORK_CONTEXT)
    assert resolve_verdict(results) == ("no_match", None)


def test_evaluate_rules_reports_every_rule():
    results = evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT)
    assert {r["rule_code"] for r in results} == {rule.code for rule in DEFAULT_GLOBAL_RULES}


def test_unmatched_rule_has_no_action_or_reason():
    results = evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT)
    unmatched = [r for r in results if not r["matched"]]
    assert unmatched
    for result in unmatched:
        assert result["action"] is None
        assert result["reason"] == ""


def test_resolve_verdict_with_no_results_is_no_match():
    assert resolve_verdict([]) == ("no_match", None)


# --- effective-date windows ---------------------------------------------


def _rule(**overrides) -> Rule:
    defaults = dict(
        code="TEST-RULE",
        rule_type="auto_approval",
        action="auto_approve",
        condition={"field": "billed_amount", "op": "gte", "value": 0},
        reason="always matches",
        priority=50,
        source="global",
    )
    return Rule(**{**defaults, **overrides})


def test_future_rule_is_ignored():
    rule = _rule(effective_from=NOW + timedelta(days=1))
    results = evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT, (rule,), as_of=NOW)
    assert results[0]["matched"] is False


def test_expired_rule_is_ignored():
    rule = _rule(effective_to=NOW - timedelta(days=1))
    results = evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT, (rule,), as_of=NOW)
    assert results[0]["matched"] is False


def test_rule_within_its_window_is_considered():
    rule = _rule(effective_from=NOW - timedelta(days=1), effective_to=NOW + timedelta(days=1))
    results = evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT, (rule,), as_of=NOW)
    assert results[0]["matched"] is True


def test_rule_with_no_window_is_always_considered():
    rule = _rule(effective_from=None, effective_to=None)
    results = evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT, (rule,), as_of=NOW)
    assert results[0]["matched"] is True


def test_effective_to_is_exclusive_at_the_boundary():
    rule = _rule(effective_to=NOW)
    results = evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT, (rule,), as_of=NOW)
    assert results[0]["matched"] is False


# --- hospital vs. global resolution --------------------------------------


def test_hospital_rule_overrides_global_even_at_lower_priority():
    hospital_rule = _rule(
        code="HOSPITAL-OVERRIDE",
        source="hospital",
        priority=1,
        action="auto_approve",
    )
    # A global rule that would also match and normally outrank by priority.
    global_rule = _rule(code="GLOBAL-DENY", source="global", priority=1000, action="auto_deny")

    action, winner = resolve_verdict(
        evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT, (hospital_rule, global_rule), as_of=NOW)
    )
    assert action == "auto_approve"
    assert winner["rule_code"] == "HOSPITAL-OVERRIDE"


def test_highest_priority_hospital_rule_wins_among_several():
    low = _rule(code="H-LOW", source="hospital", priority=10, action="require_review")
    high = _rule(code="H-HIGH", source="hospital", priority=90, action="auto_approve")

    action, winner = resolve_verdict(evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT, (low, high), as_of=NOW))
    assert action == "auto_approve"
    assert winner["rule_code"] == "H-HIGH"


def test_falls_back_to_global_when_no_hospital_rule_matches():
    hospital_rule = _rule(
        code="H-NO-MATCH",
        source="hospital",
        condition={"field": "billed_amount", "op": "gt", "value": 999999},
    )
    global_rule = _rule(code="G-MATCH", source="global", action="auto_approve")

    action, winner = resolve_verdict(
        evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT, (hospital_rule, global_rule), as_of=NOW)
    )
    assert action == "auto_approve"
    assert winner["rule_code"] == "G-MATCH"


def test_expired_hospital_rule_falls_back_to_global():
    hospital_rule = _rule(code="H-EXPIRED", source="hospital", effective_to=NOW - timedelta(days=1))
    global_rule = _rule(code="G-MATCH", source="global", action="require_review")

    action, winner = resolve_verdict(
        evaluate_rules(BASE_EXTRACTED, IN_NETWORK_CONTEXT, (hospital_rule, global_rule), as_of=NOW)
    )
    assert action == "require_review"
    assert winner["rule_code"] == "G-MATCH"


# --- rule_from_dict -------------------------------------------------------


def test_rule_from_dict_round_trips_postgres_shape():
    data = {
        "rule_id": "rule-123",
        "rule_code": "H-CUSTOM",
        "rule_type": "compliance",
        "version": 3,
        "priority": 75,
        "source": "hospital",
        "condition": {"field": "billed_amount", "op": "gt", "value": 1000},
        "action": "require_review",
        "reason": "Hospital-specific high-value review threshold.",
        "effective_from": "2026-01-01T00:00:00+00:00",
        "effective_to": None,
    }
    rule = rule_from_dict(data)

    assert rule.rule_id == "rule-123"
    assert rule.code == "H-CUSTOM"
    assert rule.version == 3
    assert rule.priority == 75
    assert rule.source == "hospital"
    assert rule.effective_from == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert rule.effective_to is None


def test_rule_from_dict_defaults_priority_and_source():
    rule = rule_from_dict(
        {
            "rule_code": "MINIMAL",
            "rule_type": "eligibility",
            "condition": {"field": "x", "op": "eq", "value": 1},
            "action": "require_review",
        }
    )
    assert rule.priority == 0
    assert rule.source == "global"
