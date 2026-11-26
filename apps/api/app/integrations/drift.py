"""Detect documentation drift vs branch head and map changed paths to sections."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DriftReport:
    full_name: str
    base_ref: str
    pinned_sha: str
    head_sha: str
    is_drifted: bool
    changed_files: list[str] = field(default_factory=list)
    sections_to_regen: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "full_name": self.full_name,
            "base_ref": self.base_ref,
            "pinned_sha": self.pinned_sha,
            "head_sha": self.head_sha,
            "is_drifted": self.is_drifted,
            "changed_files": self.changed_files,
            "sections_to_regen": self.sections_to_regen,
        }


# Heuristic path → section mapping for incremental regeneration
DEFAULT_SECTION_MAP: list[tuple[str, str]] = [
    ("README", "overview"),
    ("docs/", "overview"),
    ("src/", "architecture"),
    ("app/", "architecture"),
    ("api/", "api"),
    ("openapi", "api"),
    ("package.json", "dependencies"),
    ("pyproject.toml", "dependencies"),
    ("requirements", "dependencies"),
    ("Dockerfile", "deployment"),
    ("infra/", "deployment"),
    (".github/", "ci"),
    ("test", "testing"),
]


def map_changed_files_to_sections(
    changed_files: list[str],
    *,
    section_map: list[tuple[str, str]] | None = None,
) -> list[str]:
    mapping = section_map or DEFAULT_SECTION_MAP
    sections: list[str] = []
    for path in changed_files:
        lower = path.replace("\\", "/").lower()
        for pattern, section in mapping:
            if pattern.lower() in lower and section not in sections:
                sections.append(section)
    return sections


def compute_changed_files(pinned_tree: Path, head_tree: Path) -> list[str]:
    """Compare two working trees by relative path + content hash."""
    import hashlib

    def index(root: Path) -> dict[str, str]:
        out: dict[str, str] = {}
        if not root.exists():
            return out
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts:
                continue
            rel = str(path.relative_to(root)).replace("\\", "/")
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        return out

    left = index(pinned_tree)
    right = index(head_tree)
    changed: list[str] = []
    for key in sorted(set(left) | set(right)):
        if left.get(key) != right.get(key):
            changed.append(key)
    return changed


async def detect_drift(
    *,
    provider: Any,
    full_name: str,
    base_ref: str,
    pinned_sha: str,
    changed_files: list[str] | None = None,
) -> DriftReport:
    """Compare pinned SHA to current head of base_ref."""
    head_sha = await provider.resolve_ref(full_name, base_ref)
    is_drifted = head_sha.lower() != pinned_sha.lower()
    files = list(changed_files or [])
    sections = map_changed_files_to_sections(files) if files else ([] if not is_drifted else ["overview"])
    if is_drifted and not sections and not files:
        # Unknown file delta — regenerate overview as safe default
        sections = ["overview"]
    return DriftReport(
        full_name=full_name,
        base_ref=base_ref,
        pinned_sha=pinned_sha,
        head_sha=head_sha,
        is_drifted=is_drifted,
        changed_files=files,
        sections_to_regen=sections,
    )


def incremental_regen_plan(
    drift: DriftReport,
    *,
    all_sections: list[str] | None = None,
) -> dict[str, Any]:
    """Return which sections to regenerate given a drift report."""
    if not drift.is_drifted:
        return {
            "mode": "noop",
            "sections": [],
            "reason": "pinned SHA matches branch head",
        }
    targets = drift.sections_to_regen
    if not targets and all_sections:
        targets = list(all_sections)
    return {
        "mode": "incremental" if targets else "full",
        "sections": targets,
        "head_sha": drift.head_sha,
        "pinned_sha": drift.pinned_sha,
        "changed_files": drift.changed_files,
    }
