import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import ClaimStatus, ClaimType, FinalDecisionStatus

claim_status_enum = ENUM(ClaimStatus, name="claim_status", create_type=False)
claim_type_enum = ENUM(ClaimType, name="claim_type", create_type=False)
final_decision_status_enum = ENUM(FinalDecisionStatus, name="final_decision_status", create_type=False)


class Claim(Base):
    __tablename__ = "claims"

    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("members.member_id"), nullable=False)
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.policy_id"), nullable=False)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers_hospitals.provider_id")
    )
    status: Mapped[ClaimStatus] = mapped_column(claim_status_enum, nullable=False, default=ClaimStatus.submitted)
    claim_type: Mapped[ClaimType] = mapped_column(claim_type_enum, nullable=False)
    date_of_service: Mapped[date] = mapped_column(Date, nullable=False)
    procedure_codes: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    diagnosis_codes: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    assigned_adjuster_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    current_graph_thread_id: Mapped[str | None] = mapped_column(String(255))
    billed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    final_decision: Mapped[FinalDecisionStatus] = mapped_column(
        final_decision_status_enum, nullable=False, default=FinalDecisionStatus.pending
    )
    final_decision_reason: Mapped[str | None] = mapped_column(Text)
    final_decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
