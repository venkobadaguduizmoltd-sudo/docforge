"""Admin API schemas."""

from pydantic import BaseModel, Field

from app.schemas.auth import UserOut


class UserListOut(BaseModel):
    users: list[UserOut]


class AdminSettingsOut(BaseModel):
    retention_days: int = Field(ge=1)
    feature_flags: dict[str, bool]
    note: str
