import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import FinalDecisionStatus


class ClaimDecisionCreate(BaseModel):
    decided_by: uuid.UUID
    final_decision: FinalDecisionStatus = Field(
        ..., description="Must be 'approved', 'denied', or 'partially_approved'."
    )
    approved_amount: Decimal | None = Field(default=None, ge=0)
    reason: str = Field(..., min_length=1)
    idempotency_key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description=(
            "Client-generated key, stable across retries of the same decision "
            "(e.g. one UUID per review session). A replay with the same key and "
            "the same parameters returns the original result; the same key with "
            "different parameters is rejected."
        ),
    )
