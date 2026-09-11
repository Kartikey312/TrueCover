import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim
from app.models.enums import ClaimStatus

OPEN_STATUSES = [
    ClaimStatus.submitted,
    ClaimStatus.under_review,
    ClaimStatus.pending_documents,
    ClaimStatus.pending_adjuster_review,
]


async def get_queue(db: AsyncSession, adjuster_id: uuid.UUID | None) -> list[Claim]:
    query = select(Claim).where(Claim.status.in_(OPEN_STATUSES))

    if adjuster_id is not None:
        query = query.where(Claim.assigned_adjuster_id == adjuster_id)
    else:
        query = query.where(Claim.assigned_adjuster_id.is_(None))

    query = query.order_by(Claim.submitted_at.asc())

    result = await db.execute(query)
    return list(result.scalars().all())
