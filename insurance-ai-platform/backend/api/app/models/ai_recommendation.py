import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import AIRecommendationStatus, AIRecommendationType

ai_recommendation_type_enum = ENUM(AIRecommendationType, name="ai_recommendation_type", create_type=False)
ai_recommendation_status_enum = ENUM(AIRecommendationStatus, name="ai_recommendation_status", create_type=False)


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"

    recommendation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.claim_id", ondelete="CASCADE"), nullable=False
    )
    graph_thread_id: Mapped[str | None] = mapped_column(String(255))
    recommendation_type: Mapped[AIRecommendationType] = mapped_column(ai_recommendation_type_enum, nullable=False)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    reasoning: Mapped[str | None] = mapped_column(Text)
    supporting_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[AIRecommendationStatus] = mapped_column(
        ai_recommendation_status_enum, nullable=False, default=AIRecommendationStatus.pending_review
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
