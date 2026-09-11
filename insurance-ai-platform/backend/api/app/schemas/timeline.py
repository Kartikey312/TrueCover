import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TimelineEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: int
    event_type: str
    actor_type: str
    actor_id: uuid.UUID | None
    description: str | None
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    created_at: datetime
