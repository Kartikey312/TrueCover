import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import AIRecommendationStatus, AIRecommendationType


class AIRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recommendation_id: uuid.UUID
    claim_id: uuid.UUID
    graph_thread_id: str | None
    recommendation_type: AIRecommendationType
    confidence_score: Decimal | None
    reasoning: str | None
    supporting_evidence: dict[str, Any] | None
    model_name: str
    status: AIRecommendationStatus
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    created_at: datetime
