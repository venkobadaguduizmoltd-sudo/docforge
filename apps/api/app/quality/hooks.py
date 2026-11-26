"""Optional Vale / lychee hooks for the quality dashboard (self-hosted when present)."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class HookResult:
    tool: str
    available: bool
    ok: bool
    message: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "available": self.available,
            "ok": self.ok,
            "message": self.message,
            "details": self.details or {},
        }


def run_vale(path: Path) -> HookResult:
    binary = shutil.which("vale")
    if not binary:
        return HookResult(
            tool="vale",
            available=False,
            ok=True,
            message="vale not installed — skipped (install locally for prose lint)",
        )
    try:
        proc = subprocess.run(
            [binary, "--output=JSON", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        ok = proc.returncode == 0
        return HookResult(
            tool="vale",
            available=True,
            ok=ok,
            message="vale completed" if ok else "vale reported issues",
            details={"stdout": proc.stdout[:4000], "stderr": proc.stderr[:1000]},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return HookResult(tool="vale", available=True, ok=False, message=str(exc))


def run_lychee(path: Path) -> HookResult:
    binary = shutil.which("lychee")
    if not binary:
        return HookResult(
            tool="lychee",
            available=False,
            ok=True,
            message="lychee not installed — skipped (install locally for link checks)",
        )
    try:
        proc = subprocess.run(
            [binary, "--offline", "--no-progress", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        ok = proc.returncode == 0
        return HookResult(
            tool="lychee",
            available=True,
            ok=ok,
            message="lychee completed" if ok else "lychee reported broken links",
            details={"stdout": proc.stdout[:4000], "stderr": proc.stderr[:1000]},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return HookResult(tool="lychee", available=True, ok=False, message=str(exc))


def quality_dashboard_hooks(artifact_dir: Path) -> list[dict[str, Any]]:
    """Run available self-hosted quality tools against generated HTML if present."""
    html = artifact_dir / "preview.html"
    targets = [html] if html.exists() else [artifact_dir]
    results: list[HookResult] = []
    for target in targets:
        results.append(run_vale(target))
        results.append(run_lychee(target))
        break
    return [r.to_dict() for r in results]
