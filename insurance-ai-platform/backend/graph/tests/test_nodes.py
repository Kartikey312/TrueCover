from graph.nodes import (
    audit_log_node,
    auto_process_node,
    extraction_node,
    guardrail_node,
    human_review_node,
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


def test_guardrail_node_passes_clean_approval():
    state = {
        "reasoning_output": {"recommendation_type": "approve", "confidence_score": 0.9},
        "extracted_data": {"billed_amount": "100.00"},
    }
    result = guardrail_node(state)

    assert result["guardrail_result"]["passed"] is True
    assert result["guardrail_result"]["final_recommendation_type"] == "approve"


def test_guardrail_node_blocks_high_value_auto_approval():
    state = {
        "reasoning_output": {"recommendation_type": "approve", "confidence_score": 0.95},
        "extracted_data": {"billed_amount": "6000.00"},
    }
    result = guardrail_node(state)

    assert result["guardrail_result"]["passed"] is False
    assert "approval_ceiling_exceeded" in result["guardrail_result"]["flags"]
    assert result["guardrail_result"]["final_recommendation_type"] == "escalate"


def test_guardrail_node_blocks_low_confidence_decision():
    state = {
        "reasoning_output": {"recommendation_type": "deny", "confidence_score": 0.5},
        "extracted_data": {"billed_amount": "100.00"},
    }
    result = guardrail_node(state)

    assert "confidence_below_threshold" in result["guardrail_result"]["flags"]
    assert result["guardrail_result"]["final_recommendation_type"] == "escalate"


def test_guardrail_node_always_escalates_fraud_flags():
    state = {
        "reasoning_output": {"recommendation_type": "flag_for_fraud", "confidence_score": 0.95},
        "extracted_data": {"billed_amount": "100.00"},
    }
    result = guardrail_node(state)

    assert result["guardrail_result"]["final_recommendation_type"] == "escalate"
    assert "fraud_requires_human_review" in result["guardrail_result"]["flags"]


# --- auto_process_node / human_review_node ----------------------------------


def test_auto_process_node_approves():
    state = {"guardrail_result": {"final_recommendation_type": "approve", "reason": "ok"}}
    result = auto_process_node(state)

    assert result["final_outcome"]["final_decision"] == "approved"
    assert result["final_outcome"]["decision_path"] == "auto_process"


def test_auto_process_node_denies():
    state = {"guardrail_result": {"final_recommendation_type": "deny", "reason": "bad"}}
    result = auto_process_node(state)
    assert result["final_outcome"]["final_decision"] == "denied"


def test_human_review_node_reports_extraction_errors():
    state = {"extraction_errors": ["Missing required field: member_id"]}
    result = human_review_node(state)

    assert result["final_outcome"]["decision_path"] == "human_review"
    assert "member_id" in result["final_outcome"]["reason"]


def test_human_review_node_reports_guardrail_reason():
    state = {"guardrail_result": {"reason": "Guardrail(s) triggered: approval_ceiling_exceeded."}}
    result = human_review_node(state)
    assert "approval_ceiling_exceeded" in result["final_outcome"]["reason"]


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
