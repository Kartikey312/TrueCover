from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_member, get_current_user
from app.models.member import Member
from app.models.user import User
from app.schemas.auth import (
    MemberLoginRequest,
    MemberTokenResponse,
    StaffLoginRequest,
    StaffTokenResponse,
)
from app.schemas.member import MemberRead
from app.schemas.user import AdjusterRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=StaffTokenResponse)
async def staff_login(payload: StaffLoginRequest, db: AsyncSession = Depends(get_db)):
    user, token = await auth_service.authenticate_staff_user(db, payload.email, payload.password)
    return StaffTokenResponse(access_token=token, user=AdjusterRead.model_validate(user))


@router.get("/me", response_model=AdjusterRead)
async def staff_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/member-login", response_model=MemberTokenResponse)
async def member_login(payload: MemberLoginRequest, db: AsyncSession = Depends(get_db)):
    member, token = await auth_service.authenticate_member(db, payload.member_number, payload.date_of_birth)
    return MemberTokenResponse(access_token=token, member=MemberRead.model_validate(member))


@router.get("/member-me", response_model=MemberRead)
async def member_me(current_member: Member = Depends(get_current_member)):
    return current_member
