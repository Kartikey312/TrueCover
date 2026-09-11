import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.adjuster_queue import AdjusterQueueItem
from app.services import adjuster_service

router = APIRouter(prefix="/adjuster", tags=["adjuster"])


@router.get("/queue", response_model=list[AdjusterQueueItem])
async def get_queue(
    adjuster_id: uuid.UUID | None = Query(
        default=None,
        description="Return this adjuster's assigned open claims. Omit to see the unassigned intake queue.",
    ),
    db: AsyncSession = Depends(get_db),
):
    return await adjuster_service.get_queue(db, adjuster_id)
