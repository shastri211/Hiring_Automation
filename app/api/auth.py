import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, UserCreate, UserResponse
from app.services.auth import create_access_token, hash_password, verify_password
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


@router.post("/login", response_model=UserResponse)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    password_ok = verify_password(
        payload.password, user.hashed_password if user else _DUMMY_PASSWORD_HASH
    )
    if user is None or not user.is_active or not password_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS_DETAIL)

    token = create_access_token(user.id)
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return UserResponse.model_validate(user)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"success": True}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A user with this email already exists")

    user = User(
        email=payload.email,
        name=payload.name,
        hashed_password=hash_password(payload.password),
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
    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]
