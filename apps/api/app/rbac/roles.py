"""RBAC role definitions for DocForge."""

from enum import StrEnum


class RoleName(StrEnum):
    ADMIN = "admin"
    TEMPLATE_EDITOR = "template-editor"
    EDITOR = "editor"
    VIEWER = "viewer"


ROLE_HIERARCHY: dict[RoleName, int] = {
    RoleName.VIEWER: 10,
    RoleName.EDITOR: 20,
    RoleName.TEMPLATE_EDITOR: 30,
    RoleName.ADMIN: 100,
}

ALL_ROLES: tuple[RoleName, ...] = tuple(RoleName)


def role_at_least(user_role: RoleName, required: RoleName) -> bool:
    return ROLE_HIERARCHY[user_role] >= ROLE_HIERARCHY[required]
