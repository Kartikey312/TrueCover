import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models.enums import PolicyStatus


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_id: uuid.UUID
    member_number: str
    first_name: str
    last_name: str


class MemberPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    policy_id: uuid.UUID
    policy_number: str
    plan_name: str
    coverage_type: str
    status: PolicyStatus
    effective_date: date
    expiration_date: date | None
