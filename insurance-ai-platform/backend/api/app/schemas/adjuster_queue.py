import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ClaimStatus, ClaimType


class AdjusterQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    claim_id: uuid.UUID
    claim_number: str
    member_id: uuid.UUID
    status: ClaimStatus
    claim_type: ClaimType
    date_of_service: date
    submitted_at: datetime
    assigned_adjuster_id: uuid.UUID | None
