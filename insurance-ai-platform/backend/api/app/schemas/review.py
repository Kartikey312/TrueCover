import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.timeline import TimelineEvent


class GuardrailCheckRead(BaseModel):
    name: str
    passed: bool
    reason: str


class RuleMatchRead(BaseModel):
    rule_code: str
    rule_type: str
    action: str | None
    reason: str
    source: str
    priority: int


class SimilarClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    claim_id: uuid.UUID
    claim_number: str
    status: str
    final_decision: str
    claim_type: str
    billed_amount: Decimal | None
    date_of_service: date
    submitted_at: datetime


class ClaimReviewPacket(BaseModel):
    """Everything an adjuster needs to decide a claim awaiting human
    review. Built entirely from Postgres -- the graph's own checkpoint is
    only ever touched to resume, never to read for display.
    """

    claim_id: uuid.UUID
    claim_number: str
    status: str
    graph_thread_id: str | None

    member_name: str
    policy_number: str
    provider_name: str | None
    claim_type: str
    billed_amount: Decimal | None
    date_of_service: date

    extracted_fields: dict[str, Any]
    policy_citations: list[dict[str, Any]]
    similar_claims: list[SimilarClaimRead]

    recommendation_type: str | None
    confidence_score: Decimal | None
    reasoning: str | None

    guardrail_reason: str | None
    guardrail_checks: list[GuardrailCheckRead]

    # Matched fraud_detection/compliance rules -- the "fraud indicators"
    # panel. Empty means no such rule fired, not that fraud was ruled out.
    matched_rules: list[RuleMatchRead]

    audit_history: list[TimelineEvent]
