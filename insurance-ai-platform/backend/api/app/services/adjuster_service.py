import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim
from app.models.enums import ClaimStatus
from app.models.member import Member

OPEN_STATUSES = [
    ClaimStatus.submitted,
    ClaimStatus.under_review,
    ClaimStatus.pending_documents,
    ClaimStatus.pending_adjuster_review,
]


async def get_queue(db: AsyncSession, adjuster_id: uuid.UUID | None) -> list[dict]:
    query = (
        select(
            Claim.claim_id,
            Claim.claim_number,
            Claim.member_id,
            Member.first_name,
            Member.last_name,
            Claim.status,
            Claim.claim_type,
            Claim.billed_amount,
            Claim.date_of_service,
            Claim.submitted_at,
            Claim.assigned_adjuster_id,
        )
        .join(Member, Member.member_id == Claim.member_id)
        .where(Claim.status.in_(OPEN_STATUSES))
    )

    if adjuster_id is not None:
        query = query.where(Claim.assigned_adjuster_id == adjuster_id)
    else:
        query = query.where(Claim.assigned_adjuster_id.is_(None))

    query = query.order_by(Claim.submitted_at.asc())

    rows = (await db.execute(query)).all()
    return [
        {
            "claim_id": row.claim_id,
            "claim_number": row.claim_number,
            "member_id": row.member_id,
            "member_name": f"{row.first_name} {row.last_name}",
            "status": row.status,
            "claim_type": row.claim_type,
            "billed_amount": row.billed_amount,
            "date_of_service": row.date_of_service,
            "submitted_at": row.submitted_at,
            "assigned_adjuster_id": row.assigned_adjuster_id,
        }
        for row in rows
    ]
