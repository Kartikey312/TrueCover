"""LangGraph node implementations for the claims-processing pipeline.

Each node is a plain function `(ClaimState) -> dict`: it reads only the
state keys it needs, returns only the keys it sets (LangGraph merges the
partial update into state), and appends one entry to `audit_trail` so the
full pipeline history is reconstructable from state alone. human_review_node
is the one exception -- see its docstring.

Extraction is deterministic. `raw_input` can supply structured fields
directly, text parsed from an uploaded document (`document_text` --
already-decoded text; converting a document's bytes to text, OCR
included, is the caller's job, not the graph's -- see
app.services.storage_service.extract_text), or both -- an explicit field
always wins over a parsed one. Audio transcription is still out of
scope. Policy-document retrieval is Qdrant-backed when the caller
supplies `policy_context` (see pipeline_service._fetch_policy_context);
provider network status and hospital-override lookups are still
deterministic stand-ins for directories that don't exist yet.
"""

from decimal import Decimal, InvalidOperation
from typing import Any

from langgraph.types import interrupt

from .document_parser import extract_fields_from_text
from .guardrails import evaluate_guardrails
from .rules import DEFAULT_GLOBAL_RULES, evaluate_rules, resolve_verdict, rule_from_dict
from .state import ClaimState, make_audit_event

CLAIM_STATUS_BY_FINAL_DECISION: dict[str, str] = {
    "approved": "approved",
    "denied": "denied",
    "partially_approved": "closed",
}

REQUIRED_FIELDS = (
    "claim_id",
    "member_id",
    "policy_id",
    "claim_type",
    "date_of_service",
    "billed_amount",
    "procedure_codes",
)

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


_DOCUMENT_FILLABLE_FIELDS = ("claim_type", "date_of_service", "billed_amount", "procedure_codes", "diagnosis_codes")


def _merge_document_fields(raw: dict[str, Any]) -> dict[str, Any]:
    """Fills gaps in raw_input from document_text, if present -- an
    explicit, non-empty raw_input value always wins over a parsed one.
    """
    document_text = raw.get("document_text")
    if not document_text:
        return raw

    parsed = extract_fields_from_text(document_text)
    merged = dict(raw)
    for field in _DOCUMENT_FILLABLE_FIELDS:
        if not merged.get(field) and parsed.get(field):
            merged[field] = parsed[field]
    return merged


def extraction_node(state: ClaimState) -> dict[str, Any]:
    """Validates and normalizes claim input, filling any gaps from an
    uploaded document's text before checking for missing required fields.
    """
    raw = state.get("raw_input") or {}
    merged = _merge_document_fields(raw)

    normalized_amount = _normalize_amount(merged.get("billed_amount"))

    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field == "billed_amount":
            if normalized_amount is None:
                errors.append("billed_amount is missing or not a valid decimal")
            continue
        if not merged.get(field):
            errors.append(f"Missing required field: {field}")

    fields_from_document = sorted(f for f in _DOCUMENT_FILLABLE_FIELDS if not raw.get(f) and merged.get(f))

    extracted_data = {
        "claim_id": merged.get("claim_id"),
        "member_id": merged.get("member_id"),
        "policy_id": merged.get("policy_id"),
        "provider_id": merged.get("provider_id"),
        "claim_type": merged.get("claim_type"),
        "date_of_service": merged.get("date_of_service"),
        "billed_amount": normalized_amount,
        "procedure_codes": list(merged.get("procedure_codes") or []),
        "diagnosis_codes": list(merged.get("diagnosis_codes") or []),
        "documents": list(merged.get("documents") or []),
    }

    if errors:
        description = f"Extraction failed: {'; '.join(errors)}"
    elif fields_from_document:
        description = f"Structured input extracted and normalized (from document text: {', '.join(fields_from_document)})."
    else:
        description = "Structured input extracted and normalized."

    event = make_audit_event(
        node="extraction_node",
        event_type="extraction_failed" if errors else "extraction_completed",
        description=description,
        data={"errors": errors, "fields_from_document": fields_from_document},
    )

    return {
        "extracted_data": extracted_data,
        "extraction_errors": errors,
        "audit_trail": [event],
    }


# Deterministic placeholder for providers with a standing manual-review
# requirement (e.g. a hospital under active fraud investigation or a
# facility-specific contractual carve-out). Swap for a real hospital-rules
# lookup later without changing retrieval_node's contract.
HOSPITAL_OVERRIDE_PROVIDER_IDS: frozenset[str] = frozenset({"prov-flagged-1", "prov-flagged-2"})

# Same idea for network status: real network status comes from a provider
# directory that doesn't exist yet, so a fixed set of known-out-of-network
# ids lets fraud-detection rules (and tests/evaluation fixtures) exercise
# that path deterministically. Every other provider defaults to in-network.
OUT_OF_NETWORK_PROVIDER_IDS: frozenset[str] = frozenset({"prov-out-of-network"})


def _policy_context_items(
    claim_type: str | None, policy_chunks: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Builds the policy/coverage-terms portion of retrieved context.

    `policy_chunks` are real Qdrant search results supplied by the caller
    (see pipeline_service._fetch_policy_context). None means the caller
    didn't run a retrieval at all (graph-only tests, or Qdrant unreachable)
    -- fall back to a generic placeholder sentence, same as before Qdrant
    was wired in. An empty list is a real "nothing relevant found" answer.
    """
    if policy_chunks is None:
        return [
            {
                "source": "coverage_policy",
                "claim_type": claim_type,
                "text": f"Standard coverage terms apply to {claim_type or 'unknown'} claims.",
            }
        ]

    if not policy_chunks:
        return [
            {
                "source": "coverage_policy",
                "claim_type": claim_type,
                "text": f"No policy-document sections matched {claim_type or 'this'} claims; "
                "standard coverage terms apply.",
            }
        ]

    return [
        {
            "source": "policy_knowledge",
            "claim_type": claim_type,
            "text": chunk.get("text", ""),
            "score": chunk.get("score"),
            "citation": chunk.get("citation"),
        }
        for chunk in policy_chunks
    ]


def _retrieve_context(
    extracted_data: dict[str, Any],
    policy_chunks: list[dict[str, Any]] | None,
    anomaly_context: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    claim_type = extracted_data.get("claim_type")
    provider_id = extracted_data.get("provider_id")

    context: list[dict[str, Any]] = _policy_context_items(claim_type, policy_chunks)
    context.extend(anomaly_context or [])

    if provider_id:
        context.append(
            {
                "source": "provider_directory",
                "provider_id": provider_id,
                # Deterministic placeholder: unknown providers default to
                # in-network until the real directory lookup is wired in.
                "network_status": "out_of_network" if provider_id in OUT_OF_NETWORK_PROVIDER_IDS else "in_network",
            }
        )

        if provider_id in HOSPITAL_OVERRIDE_PROVIDER_IDS:
            context.append(
                {
                    "source": "hospital_rules",
                    "provider_id": provider_id,
                    "forces_human_review": True,
                    "reason": "This provider is subject to a standing manual-review requirement.",
                }
            )

    return context


def retrieval_node(state: ClaimState) -> dict[str, Any]:
    extracted_data = state.get("extracted_data") or {}
    policy_chunks = state.get("policy_context")
    anomaly_context = state.get("anomaly_context")
    context = _retrieve_context(extracted_data, policy_chunks, anomaly_context)

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
    """Resolves which rule (hospital-scoped, then global) governs this
    claim. `rule_definitions` is supplied by the caller from Postgres --
    active rules for this claim's provider plus the global set; absent
    means "use the hardcoded DEFAULT_GLOBAL_RULES" (graph-only tests).
    """
    extracted_data = state.get("extracted_data") or {}
    context = state.get("retrieved_context") or []

    rule_definitions = state.get("rule_definitions")
    rules = (
        tuple(rule_from_dict(d) for d in rule_definitions) if rule_definitions is not None else DEFAULT_GLOBAL_RULES
    )

    rule_results = evaluate_rules(extracted_data, context, rules)
    verdict, winning_rule = resolve_verdict(rule_results)
    matched = [r for r in rule_results if r["matched"]]

    if winning_rule:
        version_suffix = f" v{winning_rule['version']}" if winning_rule.get("version") else ""
        description = (
            f"Selected {winning_rule['source']} rule {winning_rule['rule_code']}{version_suffix}; "
            f"verdict={verdict}."
        )
    else:
        description = "No rules matched; verdict=no_match."

    event = make_audit_event(
        node="rule_resolution_node",
        event_type="rules_resolved",
        description=description,
        data={
            "matched_rules": [r["rule_code"] for r in matched],
            "verdict": verdict,
            "winning_rule_id": winning_rule.get("rule_id") if winning_rule else None,
            "winning_rule_code": winning_rule.get("rule_code") if winning_rule else None,
            "winning_rule_source": winning_rule.get("source") if winning_rule else None,
            "winning_rule_version": winning_rule.get("version") if winning_rule else None,
        },
    )

    return {
        "applicable_rules": rule_results,
        "rule_verdict": verdict,
        "winning_rule": winning_rule,
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
    """Gates automatic processing behind 8 independent deterministic checks
    (see guardrails.py). All 8 must pass; a single failure routes the
    claim to a human. Checks always run to completion so the audit trail
    captures every reason a claim was blocked, not just the first.
    """
    extracted_data = state.get("extracted_data") or {}
    applicable_rules = state.get("applicable_rules") or []
    retrieved_context = state.get("retrieved_context") or []
    reasoning_output = state.get("reasoning_output") or {}

    recommendation_type = reasoning_output.get("recommendation_type", "escalate")
    confidence_score = reasoning_output.get("confidence_score", 0.0)

    checks = evaluate_guardrails(
        extracted_data=extracted_data,
        applicable_rules=applicable_rules,
        retrieved_context=retrieved_context,
        recommendation_type=recommendation_type,
        confidence_score=confidence_score,
    )
    failed = [c for c in checks if not c.passed]
    passed = not failed

    reason = (
        "All guardrails passed; eligible for automatic processing."
        if passed
        else "Guardrail(s) failed: " + "; ".join(f"{c.name} ({c.reason})" for c in failed)
    )

    guardrail_result = {
        "passed": passed,
        "checks": [{"name": c.name, "passed": c.passed, "reason": c.reason} for c in checks],
        "failed_checks": [c.name for c in failed],
        # Only a clean pass of every check yields "approve" -- there is no
        # automatic path for anything else, denials included.
        "final_recommendation_type": "approve" if passed else "escalate",
        "reason": reason,
    }

    event = make_audit_event(
        node="guardrail_node",
        event_type="guardrail_passed" if passed else "guardrail_triggered",
        description=reason,
        data={"failed_checks": [c.name for c in failed], "checks_run": len(checks)},
    )

    return {
        "guardrail_result": guardrail_result,
        "audit_trail": [event],
    }


def auto_process_node(state: ClaimState) -> dict[str, Any]:
    """Only ever reached with an "approve" recommendation -- guardrail_node
    categorically blocks denials and every other outcome from this path
    (see guardrails.NON_ADVERSE_RECOMMENDATION_TYPES). The fallback below
    exists purely as a defensive backstop should that invariant ever break;
    it must never silently invent a decision.
    """
    guardrail_result = state.get("guardrail_result") or {}
    recommendation_type = guardrail_result.get("final_recommendation_type")

    if recommendation_type == "approve":
        final_decision = "approved"
        claim_status = "approved"
    else:
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


def _queue_reason(state: ClaimState) -> str:
    extraction_errors = state.get("extraction_errors") or []
    guardrail_result = state.get("guardrail_result") or {}

    if extraction_errors:
        return f"Incomplete extraction ({'; '.join(extraction_errors)})."
    if guardrail_result:
        return guardrail_result.get("reason", "Routed to human review.")
    return "Routed to human review."


def _build_review_packet(state: ClaimState, queue_reason: str) -> dict[str, Any]:
    """Everything an adjuster needs to decide, drawn entirely from state
    already produced upstream -- no new lookups happen here. "Similar
    claims" isn't included: that's a live Postgres query the caller
    displaying this packet performs separately.
    """
    reasoning_output = state.get("reasoning_output") or {}
    guardrail_result = state.get("guardrail_result") or {}

    return {
        "extracted_data": state.get("extracted_data") or {},
        "policy_citations": state.get("retrieved_context") or [],
        "recommendation_type": reasoning_output.get("recommendation_type"),
        "confidence_score": reasoning_output.get("confidence_score"),
        "reasoning": reasoning_output.get("reasoning"),
        "model_name": reasoning_output.get("model_name"),
        "guardrail_reason": queue_reason,
        "guardrail_checks": guardrail_result.get("checks", []),
    }


def _finalize_human_decision(decision: dict[str, Any], default_reason: str) -> dict[str, Any]:
    final_outcome = {
        "decision_path": "human_review",
        "final_decision": decision["final_decision"],
        "claim_status": CLAIM_STATUS_BY_FINAL_DECISION.get(
            decision["final_decision"], "pending_adjuster_review"
        ),
        "reason": decision.get("reason") or default_reason,
        "processed_by": decision["adjuster_id"],
    }

    event = make_audit_event(
        node="human_review_node",
        event_type="human_decision_recorded",
        description=f"Adjuster {decision['adjuster_id']} recorded decision: {decision['final_decision']}.",
        data={"final_decision": decision["final_decision"], "adjuster_id": decision["adjuster_id"]},
    )

    return {
        "final_outcome": final_outcome,
        "audit_trail": [event],
    }


def human_review_node(state: ClaimState) -> dict[str, Any]:
    """Pauses the graph and waits for an adjuster's explicit decision.

    LangGraph replays a node from the top on resume rather than continuing
    mid-function, so everything before `interrupt()` re-runs and must stay
    side-effect-free -- it only reads state and assembles the review
    packet. Because of that replay, the function never returns while
    paused (interrupt() doesn't return until resumed), so no audit event
    is appended for the pause itself; whatever drives the graph is
    responsible for recording that a pause happened. Only on resume, once
    a real decision is available, does this node return -- appending
    exactly one audit event for the decision.

    `decision` (from `Command(resume=decision)`) must be a dict with
    `final_decision`, `adjuster_id`, and optionally `reason`.
    """
    queue_reason = _queue_reason(state)
    review_packet = _build_review_packet(state, queue_reason)

    decision = interrupt(review_packet)

    return _finalize_human_decision(decision, queue_reason)


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
