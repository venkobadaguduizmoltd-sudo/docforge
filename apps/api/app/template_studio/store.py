"""In-memory template studio registry for CI/dev (Postgres via Alembic for compose)."""

from __future__ import annotations

import copy
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from app.services.templates import compute_spec_sha256
from app.template_studio.schema import validate_template_spec

TemplateStatus = Literal["draft", "published", "deprecated"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def slugify(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:128] or "template"


@dataclass
class TemplateVersionRecord:
    id: str
    version: int
    sha256: str
    spec_json: dict[str, Any]
    is_immutable: bool
    status: TemplateStatus
    changelog: str | None = None
    assets_meta: dict[str, Any] = field(default_factory=dict)
    last_test_run_ok: bool = False
    last_test_run_at: str | None = None
    last_test_run_job_id: str | None = None
    published_at: str | None = None
    created_at: str = field(default_factory=_now)

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "sha256": self.sha256,
            "spec_json": copy.deepcopy(self.spec_json),
            "is_immutable": self.is_immutable,
            "status": self.status,
            "changelog": self.changelog,
            "assets_meta": copy.deepcopy(self.assets_meta),
            "last_test_run_ok": self.last_test_run_ok,
            "last_test_run_at": self.last_test_run_at,
            "last_test_run_job_id": self.last_test_run_job_id,
            "published_at": self.published_at,
            "created_at": self.created_at,
        }


@dataclass
class TemplateRecord:
    id: str
    name: str
    slug: str
    description: str | None
    tags: list[str]
    status: TemplateStatus
    source: str  # builtin | studio | prompt | docx | clone
    current_version_id: str | None
    versions: dict[str, TemplateVersionRecord] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def current_version(self) -> TemplateVersionRecord | None:
        if self.current_version_id is None:
            return None
        return self.versions.get(self.current_version_id)

    def public_dict(self, *, include_spec: bool = False) -> dict[str, Any]:
        current = self.current_version()
        out: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "tags": list(self.tags),
            "status": self.status,
            "source": self.source,
            "current_version_id": self.current_version_id,
            "current_version": current.version if current else None,
            "sha256": current.sha256 if current else None,
            "immutable": bool(current and current.is_immutable),
            "last_test_run_ok": current.last_test_run_ok if current else False,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_spec and current is not None:
            out["spec"] = copy.deepcopy(current.spec_json)
            out["version_detail"] = current.public_dict()
        return out


_TEMPLATES: dict[str, TemplateRecord] = {}
_BY_SLUG: dict[str, str] = {}
_SEEDED = False


def reset_store() -> None:
    global _SEEDED
    _TEMPLATES.clear()
    _BY_SLUG.clear()
    _SEEDED = False


def get_template(template_id: str) -> TemplateRecord | None:
    return _TEMPLATES.get(template_id)


def get_template_by_slug(slug: str) -> TemplateRecord | None:
    tid = _BY_SLUG.get(slug)
    if tid is None:
        return None
    return _TEMPLATES.get(tid)


def list_templates(
    *,
    tag: str | None = None,
    status: TemplateStatus | None = None,
) -> list[TemplateRecord]:
    ensure_seeded_builtins()
    items = list(_TEMPLATES.values())
    if tag:
        items = [t for t in items if tag in t.tags]
    if status:
        items = [t for t in items if t.status == status]
    return sorted(items, key=lambda t: t.name.lower())


def _register(record: TemplateRecord) -> TemplateRecord:
    _TEMPLATES[record.id] = record
    _BY_SLUG[record.slug] = record.id
    return record


def create_template(
    *,
    name: str,
    slug: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    spec: dict[str, Any] | None = None,
    source: str = "studio",
    status: TemplateStatus = "draft",
    immutable: bool = False,
) -> TemplateRecord:
    ensure_seeded_builtins()
    resolved_slug = slugify(slug or name)
    if resolved_slug in _BY_SLUG:
        raise KeyError(f"slug already exists: {resolved_slug}")
    base_spec = spec or {
        "id": f"studio.{resolved_slug}",
        "name": name,
        "slug": resolved_slug,
        "description": description or "",
        "tags": list(tags or []),
        "theme": {
            "html": "theme/document.html.j2",
            "css": "theme/styles.css",
            "docx": "theme/docx-styles.json",
        },
        "sections": [
            {
                "id": "overview",
                "title": "Overview",
                "description": "High-level summary.",
                "instructions": "Summarize purpose and scope.",
            }
        ],
    }
    base_spec = copy.deepcopy(base_spec)
    base_spec["name"] = name
    base_spec["slug"] = resolved_slug
    if description is not None:
        base_spec["description"] = description
    if tags is not None:
        base_spec["tags"] = list(tags)
    validate_template_spec(base_spec)
    tid = str(uuid.uuid4())
    vid = str(uuid.uuid4())
    sha = compute_spec_sha256(base_spec)
    version = TemplateVersionRecord(
        id=vid,
        version=1,
        sha256=sha,
        spec_json=base_spec,
        is_immutable=immutable or status == "published",
        status=status,
        published_at=_now() if status == "published" else None,
    )
    record = TemplateRecord(
        id=tid,
        name=name,
        slug=resolved_slug,
        description=description,
        tags=list(tags or base_spec.get("tags") or []),
        status=status,
        source=source,
        current_version_id=vid,
        versions={vid: version},
    )
    return _register(record)


def update_metadata(
    template_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> TemplateRecord:
    record = _TEMPLATES[template_id]
    if name is not None:
        record.name = name
    if description is not None:
        record.description = description
    if tags is not None:
        record.tags = list(tags)
    record.updated_at = _now()
    current = record.current_version()
    if current and not current.is_immutable:
        current.spec_json["name"] = record.name
        if record.description is not None:
            current.spec_json["description"] = record.description
        current.spec_json["tags"] = list(record.tags)
        current.sha256 = compute_spec_sha256(current.spec_json)
        current.last_test_run_ok = False
    return record


def replace_draft_spec(template_id: str, spec: dict[str, Any]) -> TemplateRecord:
    record = _TEMPLATES[template_id]
    current = record.current_version()
    if current is None:
        raise KeyError("no current version")
    if current.is_immutable or record.status != "draft":
        raise PermissionError("published/deprecated templates are immutable; clone or create a new draft")
    spec = copy.deepcopy(spec)
    spec["slug"] = record.slug
    spec["name"] = spec.get("name") or record.name
    validate_template_spec(spec)
    current.spec_json = spec
    current.sha256 = compute_spec_sha256(spec)
    current.last_test_run_ok = False
    current.last_test_run_at = None
    current.last_test_run_job_id = None
    record.name = spec["name"]
    record.description = spec.get("description")
    record.tags = list(spec.get("tags") or record.tags)
    record.updated_at = _now()
    return record


def clone_template(template_id: str, *, new_name: str | None = None) -> TemplateRecord:
    source = _TEMPLATES[template_id]
    current = source.current_version()
    if current is None:
        raise KeyError("no current version")
    name = new_name or f"{source.name} (copy)"
    slug = slugify(name)
    base = copy.deepcopy(current.spec_json)
    base["id"] = f"studio.{slug}"
    base["name"] = name
    base["slug"] = slug
    return create_template(
        name=name,
        slug=slug,
        description=source.description,
        tags=list(source.tags),
        spec=base,
        source="clone",
        status="draft",
        immutable=False,
    )


def mark_test_run(template_id: str, *, ok: bool, job_id: str | None = None) -> TemplateRecord:
    record = _TEMPLATES[template_id]
    current = record.current_version()
    if current is None:
        raise KeyError("no current version")
    current.last_test_run_ok = ok
    current.last_test_run_at = _now()
    current.last_test_run_job_id = job_id
    record.updated_at = _now()
    return record


def publish_template(template_id: str, *, require_test_run: bool = True) -> TemplateRecord:
    record = _TEMPLATES[template_id]
    current = record.current_version()
    if current is None:
        raise KeyError("no current version")
    if record.status == "deprecated":
        raise PermissionError("cannot publish a deprecated template")
    if current.is_immutable and record.status == "published":
        return record
    if require_test_run and not current.last_test_run_ok:
        raise PermissionError("test run required before publish")
    validate_template_spec(current.spec_json)
    current.sha256 = compute_spec_sha256(current.spec_json)
    current.is_immutable = True
    current.status = "published"
    current.published_at = _now()
    record.status = "published"
    record.updated_at = _now()
    return record


def deprecate_template(template_id: str) -> TemplateRecord:
    record = _TEMPLATES[template_id]
    record.status = "deprecated"
    current = record.current_version()
    if current is not None:
        current.status = "deprecated"
        current.is_immutable = True
    record.updated_at = _now()
    return record


def resolve_spec_for_generation(slug: str) -> dict[str, Any] | None:
    """Return sealed spec dict for pipeline: {spec, sha256, theme_dir hint via slug}."""
    ensure_seeded_builtins()
    record = get_template_by_slug(slug)
    if record is None:
        return None
    current = record.current_version()
    if current is None:
        return None
    return {
        "spec": copy.deepcopy(current.spec_json),
        "sha256": current.sha256,
        "slug": record.slug,
        "status": record.status,
        "immutable": current.is_immutable,
    }


def ensure_seeded_builtins() -> None:
    """Idempotent seed from disk builtins into the studio gallery."""
    global _SEEDED
    if _SEEDED:
        return
    _SEEDED = True
    from pathlib import Path

    from app.core.config import get_settings
    from app.services.templates import load_builtin_template

    settings = get_settings()
    root = settings.resolved_templates_root / "builtin"
    if not root.exists():
        return
    for path in sorted(root.iterdir()):
        if not (path / "template.json").exists():
            continue
        slug = path.name
        if slug in _BY_SLUG:
            continue
        try:
            loaded = load_builtin_template(slug, settings.resolved_templates_root)
            spec = loaded["spec"]
            validate_template_spec(spec)
        except (FileNotFoundError, Exception):
            continue
        tags = list(spec.get("tags") or ["builtin"])
        if "builtin" not in tags:
            tags.append("builtin")
        try:
            create_template(
                name=str(spec.get("name") or slug),
                slug=slug,
                description=spec.get("description"),
                tags=tags,
                spec=spec,
                source="builtin",
                status="published",
                immutable=True,
            )
        except Exception:
            continue
