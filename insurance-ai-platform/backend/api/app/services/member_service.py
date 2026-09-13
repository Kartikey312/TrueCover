import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim
from app.models.member import Member
from app.models.policy import Policy


async def list_members(db: AsyncSession) -> list[Member]:
    result = await db.execute(select(Member).order_by(Member.last_name, Member.first_name))
    return list(result.scalars().all())


async def get_member(db: AsyncSession, member_id: uuid.UUID) -> Member:
    member = await db.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Member {member_id} not found")
    return member


async def list_member_policies(db: AsyncSession, member_id: uuid.UUID) -> list[Policy]:
    await get_member(db, member_id)
    result = await db.execute(
        select(Policy).where(Policy.member_id == member_id).order_by(Policy.effective_date.desc())
    )
    return list(result.scalars().all())


async def list_member_claims(db: AsyncSession, member_id: uuid.UUID) -> list[Claim]:
    await get_member(db, member_id)
    result = await db.execute(
        select(Claim).where(Claim.member_id == member_id).order_by(Claim.submitted_at.desc())
    )
    return list(result.scalars().all())
