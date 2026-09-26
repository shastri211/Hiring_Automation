from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from typing import Literal, Optional

from app.services.auth import normalize_user_email


class _NormalizedEmail(BaseModel):
    """Every HR-account email entering the API is normalized here, so no
    path can store or look up a non-normalized address."""

    email: str

    @field_validator("email", mode="before")
    @classmethod
    def _normalize(cls, value):
        return normalize_user_email(value if isinstance(value, str) else None)


class LoginRequest(_NormalizedEmail):
    password: str


class UserCreate(_NormalizedEmail):
    password: str
    name: str


class SignupRequest(_NormalizedEmail):
    company_name: str
    name: str
    password: str


class ResendVerificationRequest(_NormalizedEmail):
    pass


class VerifyEmailRequest(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserUpdate(BaseModel):
    role: Optional[Literal["admin", "member"]] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str = "member"
    is_active: bool = True
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationSummary(BaseModel):
    id: int
    name: str


class MeResponse(UserResponse):
    organization: OrganizationSummary
    is_platform_admin: bool = False
    must_change_password: bool = False


class ForgotPasswordRequest(_NormalizedEmail):
    pass


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
