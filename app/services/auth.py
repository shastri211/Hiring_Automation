import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt for storage."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed/legacy hash - never raise out of an auth check.
        return False


# Every token this app signs carries a `purpose` claim, and each decoder
# accepts exactly one purpose - so an email-verification link can never be
# replayed as a login session, nor a session token used to verify an email.
# A token with no purpose (e.g. a session cookie issued before purposes
# existed) is rejected by every decoder.
SESSION_PURPOSE = "session"
VERIFY_EMAIL_PURPOSE = "verify_email"

VERIFY_EMAIL_TOKEN_TTL_HOURS = 24

# Shared by signup, change-password and admin-created accounts.
MIN_PASSWORD_LENGTH = 8


def normalize_user_email(email: str | None) -> str:
    """The single normalization for HR account emails (signup, login,
    invite, resend-verification, CLI). Stored and looked up only in this
    form; users.email has a unique index on lower(email) as a second guard."""
    return (email or "").strip().lower()


def _encode(user_id: int, purpose: str, expires_delta: timedelta) -> str:
    payload = {
        "sub": str(user_id),
        "purpose": purpose,
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def _decode(token: str, purpose: str) -> int | None:
    """Returns the user id iff the token is validly signed, unexpired, and
    carries exactly `purpose`. The purpose is checked before `sub` is
    trusted. Never raises."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("purpose") != purpose:
            return None
        sub = payload.get("sub")
        if sub is None:
            return None
        return int(sub)
    except (jwt.PyJWTError, ValueError, TypeError):
        return None


def create_access_token(user_id: int) -> str:
    """Issue a signed session JWT (`purpose` = "session")."""
    return _encode(user_id, SESSION_PURPOSE, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def decode_access_token(token: str) -> int | None:
    """Decode a session token, returning the user id - None for any
    missing/invalid/expired/malformed token or any non-session purpose, so
    callers (get_authenticated_user) can uniformly turn that into a 401."""
    return _decode(token, SESSION_PURPOSE)


def create_verification_token(user_id: int) -> str:
    return _encode(user_id, VERIFY_EMAIL_PURPOSE, timedelta(hours=VERIFY_EMAIL_TOKEN_TTL_HOURS))


def decode_verification_token(token: str) -> int | None:
    """Only accepts `purpose` = "verify_email" - a session token is rejected."""
    return _decode(token, VERIFY_EMAIL_PURPOSE)
