"""FastAPI dependencies that turn a Bearer token into a verified actor.

get_current_user / get_current_member are the only places a request's
claimed identity is trusted from here on -- routes that record who did
something (a decision, an approval, an activation) must source that id
from one of these, never from a client-supplied request field, or the
whole point of authentication is defeated.
"""

import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.enums import UserRole
from app.models.member import Member
from app.models.user import User
from app.security import decode_token

_staff_bearer = HTTPBearer(auto_error=False, scheme_name="StaffBearer")
_member_bearer = HTTPBearer(auto_error=False, scheme_name="MemberBearer")

_INVALID_TOKEN = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token.")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_staff_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token.")
    try:
        claims = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise _INVALID_TOKEN

    if claims.get("kind") != "staff":
        raise _INVALID_TOKEN

    user = await db.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise _INVALID_TOKEN
    return user


def require_role(*roles: UserRole):
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"This action requires one of: {', '.join(r.value for r in roles)}.",
            )
        return current_user

    return _check


async def get_current_member(
    credentials: HTTPAuthorizationCredentials | None = Depends(_member_bearer),
    db: AsyncSession = Depends(get_db),
) -> Member:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token.")
    try:
        claims = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise _INVALID_TOKEN

    if claims.get("kind") != "member":
        raise _INVALID_TOKEN

    member = await db.get(Member, uuid.UUID(claims["sub"]))
    if member is None:
        raise _INVALID_TOKEN
    return member
