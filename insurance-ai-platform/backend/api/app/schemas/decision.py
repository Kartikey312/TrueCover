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
