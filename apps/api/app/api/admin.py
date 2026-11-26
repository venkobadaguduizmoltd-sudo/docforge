"""Admin control-plane endpoints (shell for Phases 3–4 deep UIs)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.rbac.deps import require_role
from app.rbac.roles import RoleName
from app.schemas.admin import AdminSettingsOut, UserListOut
from app.schemas.auth import UserOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=UserListOut)
def list_users(
    _admin: User = Depends(require_role(RoleName.ADMIN)),
    db: Session = Depends(get_db),
) -> UserListOut:
    users = db.scalars(select(User).order_by(User.email)).all()
    return UserListOut(users=[UserOut.model_validate(u) for u in users])


@router.get("/settings", response_model=AdminSettingsOut)
def get_settings_placeholder(
    _admin: User = Depends(require_role(RoleName.ADMIN)),
) -> AdminSettingsOut:
    from app.ai.store import get_policy, seed_default_providers

    seed_default_providers()
    policy = get_policy()
    return AdminSettingsOut(
        retention_days=90,
        feature_flags={
            "suggestion_mode": True,
            "section_locks": True,
            "paid_providers": policy.allow_paid_providers,
            "template_studio": True,
            "ai_providers": True,
        },
        note="Retention placeholders remain; providers and template studio live under /admin.",
    )
