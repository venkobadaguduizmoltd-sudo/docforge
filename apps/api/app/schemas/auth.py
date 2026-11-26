"""Auth request/response schemas."""

from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field


def _local_email(value: str) -> str:
    """Allow bootstrap emails like admin@localhost (EmailStr rejects no-dot TLDs)."""
    cleaned = value.strip()
    if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
        raise ValueError("Invalid email address")
    local, _, domain = cleaned.partition("@")
    if not local or not domain:
        raise ValueError("Invalid email address")
    return cleaned


LocalEmail = Annotated[str, AfterValidator(_local_email)]


class LoginRequest(BaseModel):
    email: LocalEmail
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: UUID
    email: LocalEmail
    full_name: str | None
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    email: LocalEmail
    password: str = Field(min_length=8)
    full_name: str | None = None
