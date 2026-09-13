from pydantic import BaseModel, ConfigDict
from datetime import datetime


class LoginRequest(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    email: str
    password: str
    name: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
