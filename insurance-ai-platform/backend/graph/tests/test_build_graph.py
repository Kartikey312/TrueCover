from graph.build_graph import build_graph


def _run(raw_input):
    graph = build_graph()
    return graph.invoke({"claim_id": raw_input.get("claim_id"), "raw_input": raw_input})


def test_full_pipeline_auto_approves_low_value_claim():
    raw_input = {
        "claim_id": "CLM-1",
        "member_id": "m1",
        "policy_id": "p1",
        "provider_id": "prov-1",
        "claim_type": "medical",
        "date_of_service": "2026-08-01",
        "billed_amount": "100.00",
        "procedure_codes": ["99213"],
        "documents": ["doc-1"],
    }

    final_state = _run(raw_input)

    assert final_state["final_outcome"]["decision_path"] == "auto_process"
    assert final_state["final_outcome"]["final_decision"] == "approved"

    node_sequence = [e["node"] for e in final_state["audit_trail"]]
    assert node_sequence == [
        "extraction_node",
        "retrieval_node",
        "rule_resolution_node",
        "reasoning_node",
        "guardrail_node",
        "auto_process_node",
        "audit_log_node",
    ]


def test_full_pipeline_denies_unrecognized_claim_type():
    raw_input = {
        "claim_id": "CLM-2",
        "member_id": "m1",
        "policy_id": "p1",
        "claim_type": "not_a_type",
        "date_of_service": "2026-08-01",
        "billed_amount": "100.00",
        "procedure_codes": ["99213"],
        "documents": ["doc-1"],
    }

    final_state = _run(raw_input)

    assert final_state["final_outcome"]["final_decision"] == "denied"
    assert final_state["final_outcome"]["decision_path"] == "auto_process"


def test_full_pipeline_routes_incomplete_input_straight_to_human_review():
    raw_input = {"claim_id": "CLM-3"}  # missing everything else

    final_state = _run(raw_input)

    assert final_state["final_outcome"]["decision_path"] == "human_review"
    node_sequence = [e["node"] for e in final_state["audit_trail"]]
    assert node_sequence == ["extraction_node", "human_review_node", "audit_log_node"]


def test_full_pipeline_escalates_high_value_claim_to_human_review():
    raw_input = {
        "claim_id": "CLM-4",
        "member_id": "m1",
        "policy_id": "p1",
        "claim_type": "medical",
        "date_of_service": "2026-08-01",
        "billed_amount": "15000.00",
        "procedure_codes": ["99213"],
        "documents": ["doc-1"],
    }

    final_state = _run(raw_input)

    assert final_state["final_outcome"]["decision_path"] == "human_review"


def test_full_pipeline_escalates_mid_range_claim_with_no_rule_match():
    # In-network (the retrieval stub's default), documented, but priced
    # between the auto-approve and high-value-review thresholds: no rule
    # fires, so reasoning_node's no_match default (escalate) should win.
    raw_input = {
        "claim_id": "CLM-5",
        "member_id": "m1",
        "policy_id": "p1",
        "provider_id": "prov-2",
        "claim_type": "medical",
        "date_of_service": "2026-08-01",
        "billed_amount": "2000.00",
        "procedure_codes": ["99213"],
        "documents": ["doc-1"],
    }

    final_state = _run(raw_input)

    assert final_state["final_outcome"]["decision_path"] == "human_review"
