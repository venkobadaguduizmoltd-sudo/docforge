"""Auth skeleton and RBAC unit tests."""

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.rbac.roles import RoleName, role_at_least


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("secret-password")
    assert hashed != "secret-password"
    assert verify_password("secret-password", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip() -> None:
    token = create_access_token("user-123", claims={"role": RoleName.EDITOR.value})
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == RoleName.EDITOR.value


def test_role_hierarchy(all_roles: tuple[RoleName, ...]) -> None:
    assert role_at_least(RoleName.ADMIN, RoleName.VIEWER)
    assert role_at_least(RoleName.TEMPLATE_EDITOR, RoleName.EDITOR)
    assert not role_at_least(RoleName.VIEWER, RoleName.EDITOR)
    assert not role_at_least(RoleName.EDITOR, RoleName.ADMIN)
    assert set(all_roles) == {
        RoleName.ADMIN,
        RoleName.TEMPLATE_EDITOR,
        RoleName.EDITOR,
        RoleName.VIEWER,
    }
