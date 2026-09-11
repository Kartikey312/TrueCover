from graph.nodes import (
    _build_review_packet,
    _finalize_human_decision,
    _queue_reason,
    audit_log_node,
    auto_process_node,
    extraction_node,
    guardrail_node,
    reasoning_node,
    retrieval_node,
    rule_resolution_node,
)

VALID_RAW_INPUT = {
    "claim_id": "CLM-TEST-1",
    "member_id": "member-1",
    "policy_id": "policy-1",
    "provider_id": "provider-1",
    "claim_type": "medical",
    "date_of_service": "2026-08-01",
    "billed_amount": "100.00",
    "procedure_codes": ["99213"],
    "diagnosis_codes": ["J06.9"],
    "documents": ["doc-1"],
}


# --- extraction_node ---------------------------------------------------


def test_extraction_node_normalizes_valid_input():
    result = extraction_node({"raw_input": VALID_RAW_INPUT})

    assert result["extraction_errors"] == []
    assert result["extracted_data"]["billed_amount"] == "100.00"
    assert result["extracted_data"]["procedure_codes"] == ["99213"]
    assert len(result["audit_trail"]) == 1
    assert result["audit_trail"][0]["event_type"] == "extraction_completed"


def test_extraction_node_flags_missing_required_fields():
    raw = {**VALID_RAW_INPUT}
    del raw["member_id"]
    raw["billed_amount"] = None

    result = extraction_node({"raw_input": raw})

    assert any("member_id" in e for e in result["extraction_errors"])
    assert any("billed_amount" in e for e in result["extraction_errors"])
    assert result["audit_trail"][0]["event_type"] == "extraction_failed"


def test_extraction_node_rejects_non_numeric_amount():
    raw = {**VALID_RAW_INPUT, "billed_amount": "not-a-number"}
    result = extraction_node({"raw_input": raw})

    assert result["extracted_data"]["billed_amount"] is None
    assert any("billed_amount" in e for e in result["extraction_errors"])


def test_extraction_node_handles_missing_raw_input():
    result = extraction_node({})
    assert result["extraction_errors"]
    assert result["extracted_data"]["claim_id"] is None


# --- retrieval_node ------------------------------------------------------


def test_retrieval_node_returns_context_for_known_provider():
    state = {"extracted_data": {"claim_type": "medical", "provider_id": "provider-1"}}
    result = retrieval_node(state)

    assert len(result["retrieved_context"]) == 2
    assert result["audit_trail"][0]["event_type"] == "context_retrieved"


def test_retrieval_node_handles_missing_provider():
    state = {"extracted_data": {"claim_type": "dental"}}
    result = retrieval_node(state)
    assert len(result["retrieved_context"]) == 1


# --- rule_resolution_node --------------------------------------------------


def test_rule_resolution_node_surfaces_verdict_and_matches():
    state = {
        "extracted_data": {"claim_type": "medical", "billed_amount": "100.00", "documents": ["d"]},
        "retrieved_context": [{"network_status": "in_network"}],
    }
    result = rule_resolution_node(state)

    assert result["rule_verdict"] == "auto_approve"
    assert any(r["matched"] for r in result["applicable_rules"])
    assert result["audit_trail"][0]["event_type"] == "rules_resolved"


# --- reasoning_node --------------------------------------------------------


def test_reasoning_node_maps_verdict_to_recommendation():
    state = {
        "rule_verdict": "auto_approve",
        "applicable_rules": [
            {
                "rule_code": "AUTO-APPROVE-LOW-VALUE",
                "matched": True,
                "reason": "ok",
                "rule_type": "auto_approval",
                "action": "auto_approve",
            }
        ],
    }
    result = reasoning_node(state)

    assert result["reasoning_output"]["recommendation_type"] == "approve"
    assert result["reasoning_output"]["confidence_score"] == 0.9
    assert "AUTO-APPROVE-LOW-VALUE" in result["reasoning_output"]["reasoning"]


def test_reasoning_node_defaults_to_escalate_on_no_match():
    result = reasoning_node({"rule_verdict": "no_match", "applicable_rules": []})
    assert result["reasoning_output"]["recommendation_type"] == "escalate"


# --- guardrail_node ---------------------------------------------------------


CLEAN_GUARDRAIL_STATE = {
    "reasoning_output": {"recommendation_type": "approve", "confidence_score": 0.9},
    "extracted_data": {
        "claim_type": "dental",
        "billed_amount": "100.00",
        "diagnosis_codes": ["K02.9"],
        "documents": ["doc-1"],
    },
    "applicable_rules": [],
    "retrieved_context": [],
}


def test_guardrail_node_passes_clean_low_value_dental_approval():
    result = guardrail_node(CLEAN_GUARDRAIL_STATE)

    assert result["guardrail_result"]["passed"] is True
    assert result["guardrail_result"]["final_recommendation_type"] == "approve"
    assert result["guardrail_result"]["failed_checks"] == []
    assert len(result["guardrail_result"]["checks"]) == 8


def test_guardrail_node_blocks_ineligible_claim_type():
    state = {**CLEAN_GUARDRAIL_STATE, "extracted_data": {**CLEAN_GUARDRAIL_STATE["extracted_data"], "claim_type": "medical"}}
    result = guardrail_node(state)

    assert result["guardrail_result"]["passed"] is False
    assert "claim_type_auto_eligible" in result["guardrail_result"]["failed_checks"]
    assert result["guardrail_result"]["final_recommendation_type"] == "escalate"


def test_guardrail_node_blocks_amount_above_cap():
    state = {**CLEAN_GUARDRAIL_STATE, "extracted_data": {**CLEAN_GUARDRAIL_STATE["extracted_data"], "billed_amount": "6000.00"}}
    result = guardrail_node(state)

    assert result["guardrail_result"]["passed"] is False
    assert "amount_below_cap" in result["guardrail_result"]["failed_checks"]


def test_guardrail_node_blocks_low_confidence_decision():
    state = {**CLEAN_GUARDRAIL_STATE, "reasoning_output": {"recommendation_type": "approve", "confidence_score": 0.5}}
    result = guardrail_node(state)

    assert "confidence_meets_threshold" in result["guardrail_result"]["failed_checks"]
    assert result["guardrail_result"]["final_recommendation_type"] == "escalate"


def test_guardrail_node_always_blocks_denials():
    state = {**CLEAN_GUARDRAIL_STATE, "reasoning_output": {"recommendation_type": "deny", "confidence_score": 0.95}}
    result = guardrail_node(state)

    assert result["guardrail_result"]["final_recommendation_type"] == "escalate"
    assert "not_adverse_determination" in result["guardrail_result"]["failed_checks"]


def test_guardrail_node_always_blocks_fraud_flags():
    state = {**CLEAN_GUARDRAIL_STATE, "reasoning_output": {"recommendation_type": "flag_for_fraud", "confidence_score": 0.95}}
    result = guardrail_node(state)

    assert result["guardrail_result"]["final_recommendation_type"] == "escalate"
    assert "not_adverse_determination" in result["guardrail_result"]["failed_checks"]


def test_guardrail_node_blocks_behavioral_health_diagnosis():
    state = {**CLEAN_GUARDRAIL_STATE, "extracted_data": {**CLEAN_GUARDRAIL_STATE["extracted_data"], "diagnosis_codes": ["F41.1"]}}
    result = guardrail_node(state)

    assert "not_behavioral_health" in result["guardrail_result"]["failed_checks"]


def test_guardrail_node_blocks_missing_documents():
    state = {**CLEAN_GUARDRAIL_STATE, "extracted_data": {**CLEAN_GUARDRAIL_STATE["extracted_data"], "documents": []}}
    result = guardrail_node(state)

    assert "required_documents_present" in result["guardrail_result"]["failed_checks"]


def test_guardrail_node_blocks_fraud_rule_match():
    state = {
        **CLEAN_GUARDRAIL_STATE,
        "applicable_rules": [
            {"rule_code": "FRAUD-X", "rule_type": "fraud_detection", "matched": True, "action": "flag_fraud", "reason": "x"},
        ],
    }
    result = guardrail_node(state)

    assert "no_fraud_or_policy_conflict" in result["guardrail_result"]["failed_checks"]


def test_guardrail_node_blocks_hospital_override():
    state = {
        **CLEAN_GUARDRAIL_STATE,
        "retrieved_context": [{"source": "hospital_rules", "forces_human_review": True}],
    }
    result = guardrail_node(state)

    assert "no_hospital_override" in result["guardrail_result"]["failed_checks"]


# --- auto_process_node / human_review_node ----------------------------------


def test_auto_process_node_approves():
    state = {"guardrail_result": {"final_recommendation_type": "approve", "reason": "ok"}}
    result = auto_process_node(state)

    assert result["final_outcome"]["final_decision"] == "approved"
    assert result["final_outcome"]["decision_path"] == "auto_process"


def test_auto_process_node_never_invents_a_denial():
    # guardrail_node never actually produces "deny" here (denials always
    # fail the not_adverse_determination check and route to human_review_node
    # instead), but auto_process_node must still degrade safely if it is.
    state = {"guardrail_result": {"final_recommendation_type": "deny", "reason": "bad"}}
    result = auto_process_node(state)

    assert result["final_outcome"]["final_decision"] == "pending"
    assert result["final_outcome"]["claim_status"] == "pending_adjuster_review"


# human_review_node itself calls interrupt(), which raises outside a
# compiled graph's runtime -- it can only be exercised end-to-end (see
# test_build_graph.py). Its pure helpers are unit tested directly here.


def test_queue_reason_reports_extraction_errors():
    state = {"extraction_errors": ["Missing required field: member_id"]}
    assert "member_id" in _queue_reason(state)


def test_queue_reason_reports_guardrail_reason():
    state = {"guardrail_result": {"reason": "Guardrail(s) triggered: approval_ceiling_exceeded."}}
    assert "approval_ceiling_exceeded" in _queue_reason(state)


def test_queue_reason_defaults_when_nothing_present():
    assert _queue_reason({}) == "Routed to human review."


def test_build_review_packet_surfaces_everything_from_state():
    state = {
        "extracted_data": {"claim_type": "dental", "billed_amount": "100.00"},
        "retrieved_context": [{"source": "coverage_policy"}],
        "reasoning_output": {
            "recommendation_type": "approve",
            "confidence_score": 0.9,
            "reasoning": "AUTO-APPROVE-LOW-VALUE: matched.",
            "model_name": "rules-engine-v1",
        },
        "guardrail_result": {"checks": [{"name": "amount_below_cap", "passed": True, "reason": ""}]},
    }
    packet = _build_review_packet(state, "some reason")

    assert packet["extracted_data"] == state["extracted_data"]
    assert packet["policy_citations"] == state["retrieved_context"]
    assert packet["recommendation_type"] == "approve"
    assert packet["confidence_score"] == 0.9
    assert packet["reasoning"] == "AUTO-APPROVE-LOW-VALUE: matched."
    assert packet["model_name"] == "rules-engine-v1"
    assert packet["guardrail_reason"] == "some reason"
    assert packet["guardrail_checks"] == state["guardrail_result"]["checks"]


def test_build_review_packet_handles_missing_state():
    packet = _build_review_packet({}, "no data yet")
    assert packet["extracted_data"] == {}
    assert packet["policy_citations"] == []
    assert packet["recommendation_type"] is None


def test_finalize_human_decision_approved():
    decision = {"final_decision": "approved", "adjuster_id": "adj-1", "reason": "Looks correct."}
    result = _finalize_human_decision(decision, "default reason")

    assert result["final_outcome"]["decision_path"] == "human_review"
    assert result["final_outcome"]["final_decision"] == "approved"
    assert result["final_outcome"]["claim_status"] == "approved"
    assert result["final_outcome"]["processed_by"] == "adj-1"
    assert result["final_outcome"]["reason"] == "Looks correct."
    assert result["audit_trail"][0]["event_type"] == "human_decision_recorded"
    assert result["audit_trail"][0]["data"]["adjuster_id"] == "adj-1"


def test_finalize_human_decision_denied():
    decision = {"final_decision": "denied", "adjuster_id": "adj-2", "reason": "Not covered."}
    result = _finalize_human_decision(decision, "default reason")

    assert result["final_outcome"]["final_decision"] == "denied"
    assert result["final_outcome"]["claim_status"] == "denied"


def test_finalize_human_decision_falls_back_to_default_reason():
    decision = {"final_decision": "approved", "adjuster_id": "adj-3"}
    result = _finalize_human_decision(decision, "queued because X")
    assert result["final_outcome"]["reason"] == "queued because X"


# --- audit_log_node ----------------------------------------------------------


def test_audit_log_node_appends_final_event():
    state = {
        "final_outcome": {"decision_path": "auto_process", "final_decision": "approved"},
        "audit_trail": [{"node": "x", "event_type": "y", "description": "z", "timestamp": "t", "data": {}}],
    }
    result = audit_log_node(state)

    assert len(result["audit_trail"]) == 1
    assert result["audit_trail"][0]["event_type"] == "pipeline_completed"
    assert result["audit_trail"][0]["data"]["event_count"] == 2
