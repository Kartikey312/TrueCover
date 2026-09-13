import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ClaimStatus, ClaimType, FinalDecisionStatus


class ClaimCreate(BaseModel):
    member_id: uuid.UUID
    policy_id: uuid.UUID
    provider_id: uuid.UUID | None = None
    claim_type: ClaimType
    date_of_service: date
    billed_amount: Decimal | None = Field(default=None, ge=0)
    # Optional at creation: a claim can be filed with just a document
    # attached (see POST /claims/{id}/documents) and these filled in from
    # its text at submit time. Anything provided here is authoritative and
    # is never overwritten by what's parsed from a document.
    procedure_codes: list[str] = Field(default_factory=list)
    diagnosis_codes: list[str] = Field(default_factory=list)


class ClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    claim_id: uuid.UUID
    claim_number: str
    member_id: uuid.UUID
    policy_id: uuid.UUID
    provider_id: uuid.UUID | None
    status: ClaimStatus
    claim_type: ClaimType
    date_of_service: date
    procedure_codes: list[str]
    diagnosis_codes: list[str]
    submitted_at: datetime
    assigned_adjuster_id: uuid.UUID | None
    current_graph_thread_id: str | None
    billed_amount: Decimal | None
    approved_amount: Decimal | None
    paid_amount: Decimal | None
    final_decision: FinalDecisionStatus
    final_decision_reason: str | None
    final_decision_at: datetime | None
    created_at: datetime
    updated_at: datetime
