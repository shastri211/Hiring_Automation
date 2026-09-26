from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.services.auth import decode_access_token, password_fingerprint_matches


async def get_authenticated_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """Resolve the logged-in HR user from the `access_token` cookie.

    401s (with no distinction in the response - all failure modes look the
    same to the caller) when the cookie is missing, the token is
    invalid/expired/not a session token, the user no longer exists, the
    account has been deactivated, its email was never verified, or the
    password has changed since the token was issued.

    Deliberately does NOT enforce must_change_password - only the three
    routes a user needs while that flag is set (GET /auth/me,
    POST /auth/change-password, POST /auth/logout) depend on this directly.
    Everything else goes through get_current_user below.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )

    token = request.cookies.get("access_token")
    if not token:
        raise unauthorized

    decoded = decode_access_token(token)
    if decoded is None:
        raise unauthorized
    user_id, password_claim = decoded

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or user.email_verified_at is None:
        raise unauthorized
    if not password_fingerprint_matches(password_claim, user.hashed_password):
        raise unauthorized

    return user


async def get_current_user(user: User = Depends(get_authenticated_user)) -> User:
    """The default auth dependency for every protected route (applied
    router-wide in app/main.py and per-route elsewhere): an authenticated
    user who is not still on an admin-issued temporary password."""
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": "password_change_required"},
        )
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Organization admin: invites/manages users and changes company settings."""
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"reason": "admin_required"})
    return user


async def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    """Platform operator - for capabilities over configuration shared by
    every tenant (LLM/embedding/SMTP/Dograh). Not the same as an org admin."""
    if not user.is_platform_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"reason": "platform_admin_required"})
    return user
