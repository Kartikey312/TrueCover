import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import RuleStatus, RuleType

rule_type_enum = ENUM(RuleType, name="rule_type", create_type=False)
rule_status_enum = ENUM(RuleStatus, name="rule_status", create_type=False)


class Rule(Base):
    __tablename__ = "rules"

    rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    rule_type: Mapped[RuleType] = mapped_column(rule_type_enum, nullable=False)
    # {"condition": {...DSL...}, "action": "auto_approve"|..., "reason": "..."}
    rule_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[RuleStatus] = mapped_column(rule_status_enum, nullable=False, default=RuleStatus.draft)
    # NULL = global rule; set = scoped to that hospital, takes precedence
    # over global rules during resolution.
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers_hospitals.provider_id", ondelete="CASCADE")
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    # Denormalized compliance sign-off; the full history is in rule_approvals.
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("rule_code", "version", name="uq_rules_code_version"),
        UniqueConstraint("rule_id", "version", name="uq_rules_id_version"),
        CheckConstraint("version > 0", name="ck_rules_version_positive"),
    )
