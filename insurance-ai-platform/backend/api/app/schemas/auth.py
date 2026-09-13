from datetime import date

from pydantic import BaseModel

from app.schemas.member import MemberRead
from app.schemas.user import AdjusterRead


class StaffLoginRequest(BaseModel):
    email: str
    password: str


class MemberLoginRequest(BaseModel):
    member_number: str
    date_of_birth: date


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StaffTokenResponse(TokenResponse):
    user: AdjusterRead


class MemberTokenResponse(TokenResponse):
    member: MemberRead
