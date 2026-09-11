import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import FinalDecisionStatus

final_decision_status_enum = ENUM(FinalDecisionStatus, name="final_decision_status", create_type=False)


class ClaimDecisionRequest(Base):
    """One row per idempotency key used against POST /claims/{id}/decision.

    A replay with the same key and the same parameters is recognized as
    the same request and short-circuits without reprocessing; a replay
    with the same key but different parameters is rejected as a conflict.
    """

    __tablename__ = "claim_decision_requests"

    idempotency_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.claim_id", ondelete="CASCADE"), nullable=False
    )
    adjuster_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    final_decision: Mapped[FinalDecisionStatus] = mapped_column(final_decision_status_enum, nullable=False)
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
