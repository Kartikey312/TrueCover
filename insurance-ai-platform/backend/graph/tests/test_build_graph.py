from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from graph.build_graph import build_graph


def _invoke(raw_input, checkpointer=None):
    graph = build_graph(checkpointer)
    config = {"configurable": {"thread_id": raw_input["claim_id"]}}
    result = graph.invoke({"claim_id": raw_input.get("claim_id"), "raw_input": raw_input}, config=config)
    return graph, config, result


def _is_paused(result) -> bool:
    return "__interrupt__" in result


def _interrupt_payload(result):
    return result["__interrupt__"][0].value


def test_full_pipeline_auto_approves_low_value_dental_claim():
    # Only dental/vision are in the guardrails' auto-eligible allowlist for
    # this release -- everything else, however clean, must go to a human.
    raw_input = {
        "claim_id": "CLM-1",
        "member_id": "m1",
        "policy_id": "p1",
        "provider_id": "prov-1",
        "claim_type": "dental",
        "date_of_service": "2026-08-01",
        "billed_amount": "100.00",
        "procedure_codes": ["D1110"],
        "documents": ["doc-1"],
    }

    _, _, result = _invoke(raw_input)

    assert not _is_paused(result)
    assert result["final_outcome"]["decision_path"] == "auto_process"
    assert result["final_outcome"]["final_decision"] == "approved"

    node_sequence = [e["node"] for e in result["audit_trail"]]
    assert node_sequence == [
        "extraction_node",
        "retrieval_node",
        "rule_resolution_node",
        "reasoning_node",
        "guardrail_node",
        "auto_process_node",
        "audit_log_node",
    ]


def test_full_pipeline_pauses_before_auto_processing_a_denial():
    # rule_resolution_node/reasoning_node still recommend "deny" for an
    # unrecognized claim type, but denials are adverse determinations --
    # guardrail_node blocks this from auto_process_node, and the graph
    # must pause at human_review_node rather than deciding on its own.
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

    graph, config, result = _invoke(raw_input)

    assert _is_paused(result)
    packet = _interrupt_payload(result)
    assert packet["recommendation_type"] == "deny"
    assert packet["extracted_data"]["claim_type"] == "not_a_type"

    final_result = graph.invoke(
        Command(resume={"final_decision": "denied", "adjuster_id": "adj-1", "reason": "Confirmed ineligible."}),
        config=config,
    )

    assert not _is_paused(final_result)
    assert final_result["final_outcome"]["decision_path"] == "human_review"
    assert final_result["final_outcome"]["final_decision"] == "denied"
    assert final_result["final_outcome"]["processed_by"] == "adj-1"

    node_sequence = [e["node"] for e in final_result["audit_trail"]]
    assert node_sequence == [
        "extraction_node",
        "retrieval_node",
        "rule_resolution_node",
        "reasoning_node",
        "guardrail_node",
        "human_review_node",
        "audit_log_node",
    ]


def test_full_pipeline_pauses_for_ineligible_claim_type():
    # An otherwise-perfect low-value claim, but "medical" is not in the
    # narrow auto-eligible allowlist -- must pause for a human.
    raw_input = {
        "claim_id": "CLM-6",
        "member_id": "m1",
        "policy_id": "p1",
        "provider_id": "prov-1",
        "claim_type": "medical",
        "date_of_service": "2026-08-01",
        "billed_amount": "100.00",
        "procedure_codes": ["99213"],
        "documents": ["doc-1"],
    }

    graph, config, result = _invoke(raw_input)

    assert _is_paused(result)
    packet = _interrupt_payload(result)
    assert "claim_type_auto_eligible" in [c["name"] for c in packet["guardrail_checks"] if not c["passed"]]

    final_result = graph.invoke(
        Command(resume={"final_decision": "approved", "adjuster_id": "adj-2", "reason": "Reviewed manually."}),
        config=config,
    )
    assert final_result["final_outcome"]["decision_path"] == "human_review"
    assert final_result["final_outcome"]["final_decision"] == "approved"


def test_full_pipeline_pauses_for_behavioral_health_diagnosis():
    raw_input = {
        "claim_id": "CLM-7",
        "member_id": "m1",
        "policy_id": "p1",
        "provider_id": "prov-1",
        "claim_type": "dental",
        "date_of_service": "2026-08-01",
        "billed_amount": "100.00",
        "procedure_codes": ["D1110"],
        "diagnosis_codes": ["F41.1"],
        "documents": ["doc-1"],
    }

    _, _, result = _invoke(raw_input)

    assert _is_paused(result)
    packet = _interrupt_payload(result)
    assert "not_behavioral_health" in [c["name"] for c in packet["guardrail_checks"] if not c["passed"]]


def test_full_pipeline_pauses_for_hospital_override():
    raw_input = {
        "claim_id": "CLM-8",
        "member_id": "m1",
        "policy_id": "p1",
        "provider_id": "prov-flagged-1",
        "claim_type": "dental",
        "date_of_service": "2026-08-01",
        "billed_amount": "100.00",
        "procedure_codes": ["D1110"],
        "documents": ["doc-1"],
    }

    _, _, result = _invoke(raw_input)

    assert _is_paused(result)
    packet = _interrupt_payload(result)
    assert "no_hospital_override" in [c["name"] for c in packet["guardrail_checks"] if not c["passed"]]


def test_full_pipeline_pauses_on_incomplete_input():
    raw_input = {"claim_id": "CLM-3"}  # missing everything else

    graph, config, result = _invoke(raw_input)

    assert _is_paused(result)
    packet = _interrupt_payload(result)
    assert "Missing required field" in packet["guardrail_reason"]

    final_result = graph.invoke(
        Command(resume={"final_decision": "denied", "adjuster_id": "adj-3", "reason": "Insufficient information."}),
        config=config,
    )

    node_sequence = [e["node"] for e in final_result["audit_trail"]]
    assert node_sequence == ["extraction_node", "human_review_node", "audit_log_node"]


def test_full_pipeline_pauses_for_high_value_claim():
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

    _, _, result = _invoke(raw_input)
    assert _is_paused(result)


def test_full_pipeline_pauses_for_mid_range_claim_with_no_rule_match():
    # In-network (the retrieval stub's default), documented, but priced
    # between the auto-approve and high-value-review thresholds: no rule
    # fires, so reasoning_node's no_match default (escalate) should win,
    # and escalate always requires a human.
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

    _, _, result = _invoke(raw_input)
    assert _is_paused(result)


def test_paused_review_resumes_from_a_separate_graph_instance():
    # Proves the paused state lives in the checkpointer/thread_id, not in
    # the compiled graph object -- the property that matters in
    # production, where the process handling the resume request is not
    # the same process (or even necessarily the same graph instance) that
    # handled the original submission.
    shared_checkpointer = MemorySaver()
    raw_input = {
        "claim_id": "CLM-9",
        "member_id": "m1",
        "policy_id": "p1",
        "claim_type": "not_a_type",
        "date_of_service": "2026-08-01",
        "billed_amount": "100.00",
        "procedure_codes": ["99213"],
        "documents": ["doc-1"],
    }

    graph_a, config, result = _invoke(raw_input, checkpointer=shared_checkpointer)
    assert _is_paused(result)

    graph_b = build_graph(shared_checkpointer)
    state = graph_b.get_state(config)
    assert state.next == ("human_review_node",)

    final_result = graph_b.invoke(
        Command(resume={"final_decision": "denied", "adjuster_id": "adj-4", "reason": "Confirmed via graph_b."}),
        config=config,
    )
    assert final_result["final_outcome"]["final_decision"] == "denied"
    assert final_result["final_outcome"]["processed_by"] == "adj-4"


def test_resuming_an_already_completed_thread_does_not_reprocess():
    # LangGraph's own checkpoint semantics: once a thread has run to
    # completion, invoking it again with a different Command(resume=...)
    # returns the original cached result rather than re-executing the
    # node or applying the new payload. This is the mechanism the API
    # layer's idempotency guard sits on top of.
    raw_input = {
        "claim_id": "CLM-10",
        "member_id": "m1",
        "policy_id": "p1",
        "claim_type": "not_a_type",
        "date_of_service": "2026-08-01",
        "billed_amount": "100.00",
        "procedure_codes": ["99213"],
        "documents": ["doc-1"],
    }

    graph, config, result = _invoke(raw_input)
    assert _is_paused(result)

    first = graph.invoke(
        Command(resume={"final_decision": "denied", "adjuster_id": "adj-5", "reason": "First decision."}),
        config=config,
    )
    assert first["final_outcome"]["final_decision"] == "denied"

    second = graph.invoke(
        Command(resume={"final_decision": "approved", "adjuster_id": "adj-6", "reason": "Conflicting retry."}),
        config=config,
    )
    assert second["final_outcome"]["final_decision"] == "denied"
    assert second["final_outcome"]["processed_by"] == "adj-5"
