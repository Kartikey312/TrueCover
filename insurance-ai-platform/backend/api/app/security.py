"""Password hashing and JWT issuance/verification.

Two disjoint token "kinds" exist -- staff (sub=user_id, role) and member
(sub=member_id) -- each with its own expiry. `decode_token` returns the
raw claims for whichever dependency (get_current_user / get_current_member)
knows how to interpret them; it never assumes which kind it received.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from app.config import settings

TokenKind = Literal["staff", "member"]


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed/legacy hash -- never let a bcrypt parse error surface
        # as an auth bypass or a 500; it's simply not a valid credential.
        return False


def create_token(*, kind: TokenKind, subject: str, expires_minutes: int, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "kind": kind,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        **(extra_claims or {}),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError (expired, malformed, bad signature) -- callers
    translate that into a 401, not this module's concern.
    """
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
