"""Authenticates staff (email + password) and members (member_number +
date_of_birth), issuing the JWT each frontend then attaches as a Bearer
token to every subsequent request.

Login failures are deliberately generic ("invalid email or password" /
"invalid member number or date of birth") so a caller can't use this
endpoint to enumerate which emails or member numbers exist.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.member import Member
from app.models.user import User
from app.security import create_token, hash_password, verify_password


async def authenticate_staff_user(db: AsyncSession, email: str, password: str) -> tuple[User, str]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active or not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")

    token = create_token(
        kind="staff",
        subject=str(user.user_id),
        expires_minutes=settings.staff_token_expire_minutes,
        extra_claims={"role": user.role.value},
    )
    return user, token


async def authenticate_member(db: AsyncSession, member_number: str, date_of_birth: date) -> tuple[Member, str]:
    result = await db.execute(select(Member).where(Member.member_number == member_number))
    member = result.scalar_one_or_none()

    if member is None or member.date_of_birth != date_of_birth:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid member number or date of birth.")

    token = create_token(
        kind="member",
        subject=str(member.member_id),
        expires_minutes=settings.member_token_expire_minutes,
    )
    return member, token


async def set_staff_password(db: AsyncSession, user: User, new_password: str) -> None:
    """Used by the demo-user seed script only -- there is no self-service
    password reset flow yet.
    """
    user.password_hash = hash_password(new_password)
    await db.commit()
