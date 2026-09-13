import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ApprovalStatus, RuleStatus, RuleType

_VALID_OPS = {"eq", "ne", "lt", "lte", "gt", "gte", "in", "not_in", "contains", "is_empty", "is_not_empty"}
_MAX_CONDITION_DEPTH = 5


def validate_condition(condition: Any, depth: int = 0) -> None:
    """Rejects malformed or dangerously deep condition trees before they
    ever reach Postgres. There is no eval/exec anywhere in this path --
    conditions are pure data, checked structurally.
    """
    if depth > _MAX_CONDITION_DEPTH:
        raise ValueError("Condition nesting is too deep.")
    if not isinstance(condition, dict):
        raise ValueError("Each condition must be an object.")

    for combinator in ("all", "any"):
        if combinator in condition:
            children = condition[combinator]
            if not isinstance(children, list) or not children:
                raise ValueError(f"'{combinator}' must be a non-empty list of conditions.")
            for child in children:
                validate_condition(child, depth + 1)
            return

    if "not" in condition:
        validate_condition(condition["not"], depth + 1)
        return

    if "field" not in condition or "op" not in condition:
        raise ValueError("A leaf condition needs 'field' and 'op'.")
    if condition["op"] not in _VALID_OPS:
        raise ValueError(f"Unknown operator '{condition['op']}'. Must be one of {sorted(_VALID_OPS)}.")


class RuleDefinitionPayload(BaseModel):
    condition: dict[str, Any]
    action: Literal["auto_approve", "auto_deny", "flag_fraud", "require_review"]
    reason: str = Field(..., min_length=1)

    @field_validator("condition")
    @classmethod
    def _validate_condition(cls, value: dict[str, Any]) -> dict[str, Any]:
        validate_condition(value)
        return value


class RuleCreate(BaseModel):
    rule_code: str = Field(..., min_length=1, max_length=100)
    rule_name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    rule_type: RuleType
    provider_id: uuid.UUID | None = Field(
        default=None, description="Hospital this rule is scoped to. Omit for a global rule."
    )
    rule_definition: RuleDefinitionPayload
    priority: int = Field(default=0, description="Higher wins among matching rules in the same scope.")
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    created_by: uuid.UUID


class RuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_id: uuid.UUID
    rule_code: str
    rule_name: str
    description: str | None
    rule_type: RuleType
    provider_id: uuid.UUID | None
    rule_definition: dict[str, Any]
    version: int
    status: RuleStatus
    priority: int
    created_by: uuid.UUID | None
    approved_by: uuid.UUID | None
    effective_from: datetime | None
    effective_to: datetime | None
    created_at: datetime
    updated_at: datetime


class RuleApprovalCreate(BaseModel):
    approver_id: uuid.UUID
    approval_status: Literal["approved", "rejected", "changes_requested"]
    comments: str | None = None


class RuleApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approval_id: uuid.UUID
    rule_id: uuid.UUID
    rule_version: int
    approver_id: uuid.UUID
    approval_status: ApprovalStatus
    comments: str | None
    reviewed_at: datetime | None
    created_at: datetime


class RuleActivateRequest(BaseModel):
    activated_by: uuid.UUID
