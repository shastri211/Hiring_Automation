import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_current_user, require_admin
from app.db.session import get_db
from app.models.organization import Organization
from app.models.settings import AppSettings
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    OrganizationSummary,
    ResendVerificationRequest,
    SignupRequest,
    UserCreate,
    UserResponse,
    UserUpdate,
    VerifyEmailRequest,
)
from app.services import rate_limit
from app.services.auth import (
    MIN_PASSWORD_LENGTH,
    create_access_token,
    create_verification_token,
    decode_verification_token,
    hash_password,
    verify_password,
)
from app.services.email import email_service
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Generic message for any login failure - never reveals whether the email
# exists in the system.
_INVALID_CREDENTIALS_DETAIL = "Incorrect email or password"

# A bcrypt hash of an arbitrary, unguessable placeholder - never matches any
# real password. Used to pay the same bcrypt cost for a nonexistent-email
# login as for a wrong-password one, so response timing can't be used to
# enumerate which emails have accounts.
_DUMMY_PASSWORD_HASH = hash_password("not-a-real-password-used-only-for-timing")

# Signup and resend-verification always answer with exactly this, whether
# or not an account exists / was created / an email was actually sent.
_CHECK_INBOX = {"status": "check_inbox"}


def _client_ip_key(prefix: str, request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    return f"{prefix}:ip:{rate_limit.hash_client_ip(ip)}"


def _require_password_strength(password: str) -> None:
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"reason": "weak_password", "message": f"Password must be at least {MIN_PASSWORD_LENGTH} characters."},
        )


def _require_valid_email(email: str) -> None:
    # Format sanity only (already normalized by the schema).
    local, _, domain = (email or "").partition("@")
    if not local or "." not in domain or " " in email or len(email) > 255:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"reason": "invalid_email", "message": "Enter a valid email address."},
        )


async def _me(db: AsyncSession, user: User) -> MeResponse:
    org = (await db.execute(select(Organization).where(Organization.id == user.organization_id))).scalar_one()
    return MeResponse(
        **UserResponse.model_validate(user).model_dump(),
        organization=OrganizationSummary(id=org.id, name=org.name),
        is_platform_admin=user.is_platform_admin,
        must_change_password=user.must_change_password,
    )


async def _send_verification_email(user_id: int, email: str) -> None:
    """Best effort: an SMTP failure is logged (user id only) and swallowed -
    the account stays, and the user recovers via resend-verification."""
    if not settings.PUBLIC_APP_BASE_URL:
        logger.warning(
            "PUBLIC_APP_BASE_URL is not set - can't build an email verification link for user %s.", user_id
        )
        return
    link = f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}/verify-email?token={create_verification_token(user_id)}"
    body = (
        "Welcome to RecruitPro.\n\n"
        "Confirm your email address to activate your company account:\n"
        f"{link}\n\n"
        "This link expires in 24 hours. If you didn't sign up, you can ignore this email."
    )
    try:
        await email_service.provider.send_email(email, "Confirm your email address", body)
    except Exception:
        logger.warning("Verification email could not be sent for user %s.", user_id, exc_info=True)


# -- session ------------------------------------------------------------------

@router.post("/login", response_model=MeResponse)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    password_ok = verify_password(
        payload.password, user.hashed_password if user else _DUMMY_PASSWORD_HASH
    )
    if user is None or not user.is_active or not password_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS_DETAIL)

    # Only reachable with the correct password, so it can't be used to
    # discover which emails have (unverified) accounts.
    if user.email_verified_at is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"reason": "email_not_verified"})

    token = create_access_token(user.id)
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return await _me(db, user)


@router.post("/logout")
async def logout(response: Response):
    # No auth dependency: clearing the cookie must work even for an
    # expired/invalid session.
    response.delete_cookie("access_token")
    return {"success": True}


# get_authenticated_user (not get_current_user): must stay reachable while
# must_change_password is set, so the frontend can route to the
# change-password screen.
@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_authenticated_user), db: AsyncSession = Depends(get_db)):
    return await _me(db, current_user)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"reason": "wrong_current_password"})
    _require_password_strength(payload.new_password)
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"reason": "same_password", "message": "Choose a password different from the current one."},
        )
    current_user.hashed_password = hash_password(payload.new_password)
    current_user.must_change_password = False
    await db.commit()
    return {"success": True}


# -- self-service company signup + email verification ------------------------

@router.post("/signup", status_code=status.HTTP_202_ACCEPTED)
async def signup(payload: SignupRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await rate_limit.enforce(_client_ip_key("signup", request), settings.SIGNUP_MAX_PER_IP_PER_HOUR)

    company_name = (payload.company_name or "").strip()
    name = (payload.name or "").strip()
    if not company_name or len(company_name) > 255:
        raise HTTPException(status_code=422, detail={"reason": "invalid_company_name", "message": "Enter your company name."})
    if not name or len(name) > 255:
        raise HTTPException(status_code=422, detail={"reason": "invalid_name", "message": "Enter your name."})
    _require_valid_email(payload.email)
    _require_password_strength(payload.password)

    # Existing account (verified or not): internal no-op, same response.
    existing = (await db.execute(select(User.id).where(User.email == payload.email))).scalar_one_or_none()
    if existing is not None:
        return _CHECK_INBOX

    org = Organization(name=company_name)
    db.add(org)
    await db.flush()
    user = User(
        organization_id=org.id,
        email=payload.email,
        name=name,
        hashed_password=hash_password(payload.password),
        role="admin",
        email_verified_at=None,
    )
    db.add(user)
    db.add(AppSettings(organization_id=org.id))
    try:
        await db.commit()
    except IntegrityError:
        # Lost a race with a concurrent signup for the same email - nothing
        # of this attempt is kept; same generic response.
        await db.rollback()
        return _CHECK_INBOX

    logger.info("Signup: created organization %s with admin user %s (unverified).", org.id, user.id)
    await _send_verification_email(user.id, user.email)
    return _CHECK_INBOX


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    user_id = decode_verification_token(payload.token)  # purpose-checked
    user = None
    if user_id is not None:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"reason": "invalid_or_expired_token"})
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
        await db.commit()
    return {"status": "verified"}


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(
    payload: ResendVerificationRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    await rate_limit.enforce(
        _client_ip_key("resend", request), settings.VERIFY_RESEND_MAX_PER_IP_PER_HOUR
    )
    # Per-email limit keyed on a hash - the address never appears in Redis.
    await rate_limit.enforce(
        f"resend:email:{rate_limit.hash_identifier(payload.email)}",
        settings.VERIFY_RESEND_MAX_PER_EMAIL_PER_HOUR,
    )
    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if user is not None and user.is_active and user.email_verified_at is None:
        await _send_verification_email(user.id, user.email)
    return _CHECK_INBOX


# -- organization user management ---------------------------------------------

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin creates a teammate in their own organization with a temporary
    password they share out-of-band. The account is verified (the admin
    vouches for it) but must change that password on first login."""
    _require_valid_email(payload.email)
    _require_password_strength(payload.password)
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail={"reason": "invalid_name", "message": "Name is required."})

    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A user with this email already exists")

    user = User(
        organization_id=current_user.organization_id,
        email=payload.email,
        name=name,
        hashed_password=hash_password(payload.password),
        role="member",
        email_verified_at=datetime.now(timezone.utc),
        must_change_password=True,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A user with this email already exists")

    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(User).where(User.organization_id == current_user.organization_id).order_by(User.created_at)
    )
    return [UserResponse.model_validate(u) for u in result.scalars().all()]


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    organization_id = current_user.organization_id

    # Serialize every membership change within this organization: whoever
    # holds this row lock sees the other's committed result before counting
    # admins, so two concurrent demotions can't both leave zero admins.
    await db.execute(select(Organization.id).where(Organization.id == organization_id).with_for_update())

    target = (
        await db.execute(
            select(User)
            .where(User.id == user_id, User.organization_id == organization_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    new_role: Optional[str] = payload.role if payload.role is not None else target.role
    new_active: bool = payload.is_active if payload.is_active is not None else target.is_active

    loses_admin = target.role == "admin" and target.is_active and (new_role != "admin" or not new_active)
    if loses_admin:
        other_active_admins = (
            await db.execute(
                select(func.count(User.id)).where(
                    User.organization_id == organization_id,
                    User.role == "admin",
                    User.is_active.is_(True),
                    User.id != target.id,
                )
            )
        ).scalar_one()
        if other_active_admins == 0:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"reason": "last_admin", "message": "An organization must keep at least one active admin."},
            )

    target.role = new_role
    target.is_active = new_active
    await db.commit()
    await db.refresh(target)
    return UserResponse.model_validate(target)
