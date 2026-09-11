import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent
from app.models.enums import ActorType


async def record_event(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    event_type: str,
    actor_type: ActorType = ActorType.system,
    actor_id: uuid.UUID | None = None,
    description: str | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        description=description,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(event)
    await db.flush()
    return event
