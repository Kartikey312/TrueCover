import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.claim import ClaimRead
from app.schemas.member import MemberPolicyRead, MemberRead
from app.services import member_service

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=list[MemberRead])
async def list_members(db: AsyncSession = Depends(get_db)):
    """Backs the 'signed in as' picker in the member portal -- there's no
    login system yet, same stand-in pattern as GET /adjuster/list.
    """
    return await member_service.list_members(db)


@router.get("/{member_id}/policies", response_model=list[MemberPolicyRead])
async def list_member_policies(member_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await member_service.list_member_policies(db, member_id)


@router.get("/{member_id}/claims", response_model=list[ClaimRead])
async def list_member_claims(member_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await member_service.list_member_claims(db, member_id)
