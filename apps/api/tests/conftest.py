"""Pytest fixtures using an in-memory SQLite stand-in where Postgres-specific types allow.

Phase 0 auth and immutability tests use lightweight fakes / pure functions so
CI does not require a live Postgres. Integration tests against compose are
deferred to later phases.
"""

import uuid
from datetime import UTC, datetime

import pytest

from app.models.template import TemplateVersion
from app.rbac.roles import RoleName


@pytest.fixture
def draft_template_version() -> TemplateVersion:
    return TemplateVersion(
        id=uuid.uuid4(),
        template_id=uuid.uuid4(),
        version=1,
        sha256="0" * 64,
        spec_json={"sections": [{"id": "intro"}]},
        is_immutable=False,
        published_at=None,
    )


@pytest.fixture
def published_template_version() -> TemplateVersion:
    return TemplateVersion(
        id=uuid.uuid4(),
        template_id=uuid.uuid4(),
        version=1,
        sha256="a" * 64,
        spec_json={"sections": [{"id": "intro"}]},
        is_immutable=True,
        published_at=datetime.now(UTC),
    )


@pytest.fixture
def all_roles() -> tuple[RoleName, ...]:
    return (
        RoleName.ADMIN,
        RoleName.TEMPLATE_EDITOR,
        RoleName.EDITOR,
        RoleName.VIEWER,
    )
