import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_member
from app.models.member import Member
from app.schemas.claim import ClaimRead
from app.schemas.member import MemberPolicyRead
from app.services import member_service

router = APIRouter(prefix="/members", tags=["members"])


def _require_self(member_id: uuid.UUID, current_member: Member) -> None:
    if current_member.member_id != member_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only view your own records.")


@router.get("/{member_id}/policies", response_model=list[MemberPolicyRead])
async def list_member_policies(
    member_id: uuid.UUID,
    current_member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _require_self(member_id, current_member)
    return await member_service.list_member_policies(db, member_id)


@router.get("/{member_id}/claims", response_model=list[ClaimRead])
async def list_member_claims(
    member_id: uuid.UUID,
    current_member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _require_self(member_id, current_member)
    return await member_service.list_member_claims(db, member_id)
