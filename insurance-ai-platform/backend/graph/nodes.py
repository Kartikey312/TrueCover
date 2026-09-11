"""LangGraph node implementations for the claims-processing pipeline.

Each node is a plain function `(ClaimState) -> dict`: it reads only the
state keys it needs, returns only the keys it sets (LangGraph merges the
partial update into state), and always appends one entry to `audit_trail`
so the full pipeline history is reconstructable from state alone.

Extraction here is deterministic and expects already-structured input
(`raw_input` as a dict). OCR, vision, and audio transcription are future
upgrades to extraction_node's input handling and are intentionally out of
scope until the graph's mechanics are proven reliable. Retrieval is a
hardcoded stand-in for a future Qdrant-backed lookup; the node's
input/output contract won't need to change when that's wired in.
"""

from decimal import Decimal, InvalidOperation
from typing import Any

from .rules import evaluate_rules, resolve_verdict
from .state import ClaimState, make_audit_event

REQUIRED_FIELDS = (
    "claim_id",
    "member_id",
    "policy_id",
    "claim_type",
    "date_of_service",
    "billed_amount",
    "procedure_codes",
)

# Hard safety ceiling enforced independently of whatever business rules
# said -- deliberately decoupled from rules.py's thresholds.
HARD_APPROVAL_CEILING = Decimal("5000")
MIN_CONFIDENCE_FOR_AUTO_DECISION = 0.75

RECOMMENDATION_BY_VERDICT: dict[str, str] = {
    "auto_approve": "approve",
    "auto_deny": "deny",
    "flag_fraud": "flag_for_fraud",
    "require_review": "escalate",
    "no_match": "escalate",
}

CONFIDENCE_BY_VERDICT: dict[str, float] = {
    "auto_approve": 0.9,
    "auto_deny": 0.9,
    "flag_fraud": 0.85,
    "require_review": 0.6,
    "no_match": 0.4,
}


def _normalize_amount(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except InvalidOperation:
        return None


def extraction_node(state: ClaimState) -> dict[str, Any]:
    """Validates and normalizes structured claim input."""
    raw = state.get("raw_input") or {}

    normalized_amount = _normalize_amount(raw.get("billed_amount"))

    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field == "billed_amount":
            if normalized_amount is None:
                errors.append("billed_amount is missing or not a valid decimal")
            continue
        if not raw.get(field):
            errors.append(f"Missing required field: {field}")

    extracted_data = {
        "claim_id": raw.get("claim_id"),
        "member_id": raw.get("member_id"),
        "policy_id": raw.get("policy_id"),
        "provider_id": raw.get("provider_id"),
        "claim_type": raw.get("claim_type"),
        "date_of_service": raw.get("date_of_service"),
        "billed_amount": normalized_amount,
        "procedure_codes": list(raw.get("procedure_codes") or []),
        "diagnosis_codes": list(raw.get("diagnosis_codes") or []),
        "documents": list(raw.get("documents") or []),
    }

    event = make_audit_event(
        node="extraction_node",
        event_type="extraction_failed" if errors else "extraction_completed",
        description=(
            f"Extraction failed: {'; '.join(errors)}"
            if errors
            else "Structured input extracted and normalized."
        ),
        data={"errors": errors},
    )

    return {
        "extracted_data": extracted_data,
        "extraction_errors": errors,
        "audit_trail": [event],
    }


def _retrieve_context(extracted_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Deterministic stand-in for a future Qdrant-backed retriever."""
    claim_type = extracted_data.get("claim_type")
    provider_id = extracted_data.get("provider_id")

    context: list[dict[str, Any]] = [
        {
            "source": "coverage_policy",
            "claim_type": claim_type,
            "text": f"Standard coverage terms apply to {claim_type or 'unknown'} claims.",
        }
    ]

    if provider_id:
        context.append(
            {
                "source": "provider_directory",
                "provider_id": provider_id,
                # Deterministic placeholder: unknown providers default to
                # in-network until the real directory lookup is wired in.
                "network_status": "in_network",
            }
        )

    return context


def retrieval_node(state: ClaimState) -> dict[str, Any]:
    extracted_data = state.get("extracted_data") or {}
    context = _retrieve_context(extracted_data)

    event = make_audit_event(
        node="retrieval_node",
        event_type="context_retrieved",
        description=f"Retrieved {len(context)} grounding context item(s).",
        data={"context_sources": [item.get("source") for item in context]},
    )

    return {
        "retrieved_context": context,
        "audit_trail": [event],
    }


def rule_resolution_node(state: ClaimState) -> dict[str, Any]:
    extracted_data = state.get("extracted_data") or {}
    context = state.get("retrieved_context") or []

    rule_results = evaluate_rules(extracted_data, context)
    verdict = resolve_verdict(rule_results)
    matched = [r for r in rule_results if r["matched"]]

    event = make_audit_event(
        node="rule_resolution_node",
        event_type="rules_resolved",
        description=(
            f"{len(matched)} rule(s) matched; verdict={verdict}."
            if matched
            else "No rules matched; verdict=no_match."
        ),
        data={"matched_rules": [r["rule_code"] for r in matched], "verdict": verdict},
    )

    return {
        "applicable_rules": rule_results,
        "rule_verdict": verdict,
        "audit_trail": [event],
    }


def reasoning_node(state: ClaimState) -> dict[str, Any]:
    verdict = state.get("rule_verdict", "no_match")
    matched_rules = [r for r in state.get("applicable_rules") or [] if r["matched"]]

    recommendation_type = RECOMMENDATION_BY_VERDICT.get(verdict, "escalate")
    confidence_score = CONFIDENCE_BY_VERDICT.get(verdict, 0.4)

    if matched_rules:
        reasoning = "; ".join(f"{r['rule_code']}: {r['reason']}" for r in matched_rules)
    else:
        reasoning = "No business rule matched this claim; defaulting to human review."

    reasoning_output = {
        "recommendation_type": recommendation_type,
        "confidence_score": confidence_score,
        "reasoning": reasoning,
        "model_name": "rules-engine-v1",
    }

    event = make_audit_event(
        node="reasoning_node",
        event_type="recommendation_generated",
        description=f"Recommendation: {recommendation_type} (confidence={confidence_score}).",
        data={"recommendation_type": recommendation_type, "confidence_score": confidence_score},
    )

    return {
        "reasoning_output": reasoning_output,
        "audit_trail": [event],
    }


def guardrail_node(state: ClaimState) -> dict[str, Any]:
    reasoning_output = state.get("reasoning_output") or {}
    extracted_data = state.get("extracted_data") or {}

    recommendation_type = reasoning_output.get("recommendation_type", "escalate")
    confidence_score = reasoning_output.get("confidence_score", 0.0)

    try:
        raw_amount = extracted_data.get("billed_amount")
        billed_amount = Decimal(raw_amount) if raw_amount is not None else None
    except InvalidOperation:
        billed_amount = None

    flags: list[str] = []
    final_recommendation_type = recommendation_type

    if recommendation_type == "approve" and billed_amount is not None and billed_amount > HARD_APPROVAL_CEILING:
        flags.append("approval_ceiling_exceeded")
        final_recommendation_type = "escalate"

    if recommendation_type in ("approve", "deny") and confidence_score < MIN_CONFIDENCE_FOR_AUTO_DECISION:
        flags.append("confidence_below_threshold")
        final_recommendation_type = "escalate"

    if recommendation_type == "flag_for_fraud":
        # Fraud flags always require a human -- never auto-processed.
        flags.append("fraud_requires_human_review")
        final_recommendation_type = "escalate"

    passed = not flags
    reason = (
        "Recommendation cleared all guardrails."
        if passed
        else f"Guardrail(s) triggered: {', '.join(flags)}."
    )

    guardrail_result = {
        "passed": passed,
        "final_recommendation_type": final_recommendation_type,
        "flags": flags,
        "reason": reason,
    }

    event = make_audit_event(
        node="guardrail_node",
        event_type="guardrail_passed" if passed else "guardrail_triggered",
        description=reason,
        data={"flags": flags, "final_recommendation_type": final_recommendation_type},
    )

    return {
        "guardrail_result": guardrail_result,
        "audit_trail": [event],
    }


def auto_process_node(state: ClaimState) -> dict[str, Any]:
    guardrail_result = state.get("guardrail_result") or {}
    recommendation_type = guardrail_result.get("final_recommendation_type")

    if recommendation_type == "approve":
        final_decision = "approved"
        claim_status = "approved"
    elif recommendation_type == "deny":
        final_decision = "denied"
        claim_status = "denied"
    else:
        # Defensive fallback: this node should only be reached for
        # approve/deny, but it must never silently invent a decision.
        final_decision = "pending"
        claim_status = "pending_adjuster_review"

    final_outcome = {
        "decision_path": "auto_process",
        "final_decision": final_decision,
        "claim_status": claim_status,
        "reason": guardrail_result.get("reason", ""),
        "processed_by": "system",
    }

    event = make_audit_event(
        node="auto_process_node",
        event_type="auto_processed",
        description=f"Claim auto-processed: {final_decision}.",
        data={"final_decision": final_decision},
    )

    return {
        "final_outcome": final_outcome,
        "audit_trail": [event],
    }


def human_review_node(state: ClaimState) -> dict[str, Any]:
    extraction_errors = state.get("extraction_errors") or []
    guardrail_result = state.get("guardrail_result") or {}

    if extraction_errors:
        reason = f"Routed to human review: incomplete extraction ({'; '.join(extraction_errors)})."
    elif guardrail_result:
        reason = guardrail_result.get("reason", "Routed to human review.")
    else:
        reason = "Routed to human review."

    final_outcome = {
        "decision_path": "human_review",
        "final_decision": "pending",
        "claim_status": "pending_adjuster_review",
        "reason": reason,
        "processed_by": "system",
    }

    event = make_audit_event(
        node="human_review_node",
        event_type="queued_for_human_review",
        description=reason,
        data={},
    )

    return {
        "final_outcome": final_outcome,
        "audit_trail": [event],
    }


def audit_log_node(state: ClaimState) -> dict[str, Any]:
    final_outcome = state.get("final_outcome") or {}
    audit_trail = state.get("audit_trail") or []

    event = make_audit_event(
        node="audit_log_node",
        event_type="pipeline_completed",
        description=(
            f"Pipeline completed via {final_outcome.get('decision_path', 'unknown')} "
            f"path with decision={final_outcome.get('final_decision', 'unknown')}."
        ),
        data={
            "decision_path": final_outcome.get("decision_path"),
            "final_decision": final_outcome.get("final_decision"),
            "event_count": len(audit_trail) + 1,
        },
    )

    return {
        "audit_trail": [event],
    }
