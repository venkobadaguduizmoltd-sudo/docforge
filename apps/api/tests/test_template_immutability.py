"""Template immutability rule stub tests."""

import pytest

from app.models.template import TemplateVersion
from app.services.templates import (
    TemplateImmutabilityError,
    assert_version_mutable,
    compute_spec_sha256,
    update_draft_spec,
)


def test_compute_spec_sha256_stable() -> None:
    a = compute_spec_sha256({"b": 1, "a": 2})
    b = compute_spec_sha256({"a": 2, "b": 1})
    assert a == b
    assert len(a) == 64


def test_draft_version_can_be_updated(draft_template_version: TemplateVersion) -> None:
    assert_version_mutable(draft_template_version)


def test_published_version_is_immutable(published_template_version: TemplateVersion) -> None:
    with pytest.raises(TemplateImmutabilityError):
        assert_version_mutable(published_template_version)


class _FakeSession:
    def add(self, _obj: object) -> None:
        return None

    def flush(self) -> None:
        return None


def test_update_draft_spec_rejects_published(published_template_version: TemplateVersion) -> None:
    with pytest.raises(TemplateImmutabilityError):
        update_draft_spec(_FakeSession(), published_template_version, {"sections": []})


def test_update_draft_spec_ok(draft_template_version: TemplateVersion) -> None:
    new_spec = {"sections": [{"id": "summary"}]}
    updated = update_draft_spec(_FakeSession(), draft_template_version, new_spec)
    assert updated.spec_json == new_spec
    assert updated.sha256 == compute_spec_sha256(new_spec)
