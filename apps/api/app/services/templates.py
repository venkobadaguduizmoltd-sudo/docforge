"""Template immutability rules — published versions must not be mutated."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.template import TemplateVersion


class TemplateImmutabilityError(Exception):
    """Raised when an attempt is made to mutate a published template version."""


def compute_spec_sha256(spec_json: dict[str, Any]) -> str:
    payload = json.dumps(spec_json, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def assert_version_mutable(version: TemplateVersion) -> None:
    if version.is_immutable and version.published_at is not None:
        raise TemplateImmutabilityError(
            f"Template version {version.id} is immutable; create a new version instead"
        )


def update_draft_spec(db: Session, version: TemplateVersion, spec_json: dict[str, Any]) -> TemplateVersion:
    """Update spec only when the version is still a draft (not published/immutable)."""
    assert_version_mutable(version)
    version.spec_json = spec_json
    version.sha256 = compute_spec_sha256(spec_json)
    db.add(version)
    db.flush()
    return version


def publish_version(db: Session, version: TemplateVersion) -> TemplateVersion:
    """Mark a version immutable and seal its checksum."""
    from datetime import UTC, datetime

    version.sha256 = compute_spec_sha256(version.spec_json)
    version.is_immutable = True
    version.published_at = datetime.now(UTC)
    db.add(version)
    db.flush()
    return version
