"""Typed state shared across the claims-processing LangGraph pipeline.

The graph is pure and DB-free: nodes read and return plain dicts matching
this schema, and `audit_trail` accumulates via a LangGraph reducer so the
full run history is reconstructable from the final state alone. Persisting
that history (and the final recommendation) into Postgres' audit_events /
ai_recommendations tables is left to whatever calls the compiled graph.
"""

import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, TypedDict


class AuditEvent(TypedDict):
    node: str
    event_type: str
    description: str
    timestamp: str
    data: dict[str, Any]


def make_audit_event(
    *,
    node: str,
    event_type: str,
    description: str,
    data: dict[str, Any] | None = None,
) -> AuditEvent:
    return AuditEvent(
        node=node,
        event_type=event_type,
        description=description,
        timestamp=datetime.now(timezone.utc).isoformat(),
        data=data or {},
    )


class RuleResult(TypedDict):
    rule_id: str | None
    rule_code: str
    rule_type: str
    version: int | None
    source: Literal["global", "hospital"]
    priority: int
    matched: bool
    action: str | None
    reason: str


class ReasoningOutput(TypedDict):
    recommendation_type: Literal["approve", "deny", "request_more_info", "flag_for_fraud", "escalate"]
    confidence_score: float
    reasoning: str
    model_name: str


class GuardrailCheckResult(TypedDict):
    name: str
    passed: bool
    reason: str


class GuardrailResult(TypedDict):
    passed: bool
    checks: list[GuardrailCheckResult]
    failed_checks: list[str]
    final_recommendation_type: str
    reason: str


class FinalOutcome(TypedDict):
    decision_path: Literal["auto_process", "human_review"]
    final_decision: Literal["pending", "approved", "denied", "partially_approved"]
    claim_status: str
    reason: str
    processed_by: str


class ClaimState(TypedDict, total=False):
    claim_id: str
    raw_input: dict[str, Any]

    # Active rules for this claim (global + the claim's hospital, already
    # filtered to status='active'), supplied by the caller from Postgres.
    # Absent (key missing) means "use rules.DEFAULT_GLOBAL_RULES" -- an
    # empty list is a real "no rules configured" answer, not a signal to
    # fall back.
    rule_definitions: list[dict[str, Any]]

    # Policy-document chunks retrieved from Qdrant for this claim's plan
    # and claim type, supplied by the caller. None (key absent) means "not
    # supplied" -- retrieval_node then falls back to a generic placeholder
    # sentence (graph-only tests). An empty list is a real "nothing
    # relevant found" answer, not a signal to fall back.
    policy_context: list[dict[str, Any]] | None

    extracted_data: dict[str, Any]
    extraction_errors: list[str]

    retrieved_context: list[dict[str, Any]]

    applicable_rules: list[RuleResult]
    rule_verdict: str
    winning_rule: RuleResult | None

    reasoning_output: ReasoningOutput
    guardrail_result: GuardrailResult
    final_outcome: FinalOutcome

    audit_trail: Annotated[list[AuditEvent], operator.add]
