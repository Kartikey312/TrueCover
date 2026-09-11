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
    rule_code: str
    rule_type: str
    matched: bool
    action: str | None
    reason: str


class ReasoningOutput(TypedDict):
    recommendation_type: Literal["approve", "deny", "request_more_info", "flag_for_fraud", "escalate"]
    confidence_score: float
    reasoning: str
    model_name: str


class GuardrailResult(TypedDict):
    passed: bool
    final_recommendation_type: str
    flags: list[str]
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

    extracted_data: dict[str, Any]
    extraction_errors: list[str]

    retrieved_context: list[dict[str, Any]]

    applicable_rules: list[RuleResult]
    rule_verdict: str

    reasoning_output: ReasoningOutput
    guardrail_result: GuardrailResult
    final_outcome: FinalOutcome

    audit_trail: Annotated[list[AuditEvent], operator.add]
