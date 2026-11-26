"""`.docignore` — gitignore-like paths excluded from analysis / prompt blobs."""

from __future__ import annotations

import fnmatch
from pathlib import Path

DEFAULT_DOCIGNORE = """\
# DocForge — paths never sent to the LLM / extractors
.env
.env.*
*.pem
*.key
**/secrets/**
**/credentials/**
**/*secret*
**/id_rsa*
**/id_ed25519*
"""


def load_docignore(root: Path) -> list[str]:
    """Load patterns from `<root>/.docignore`, falling back to built-in defaults."""
    path = root / ".docignore"
    if path.is_file():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        lines = DEFAULT_DOCIGNORE.splitlines()
    patterns: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(stripped)
    return patterns


def is_ignored(rel_path: str, patterns: list[str]) -> bool:
    """Return True if relative POSIX path matches any docignore pattern."""
    path = rel_path.lstrip("./")
    for pattern in patterns:
        pat = pattern.lstrip("./")
        if pat.endswith("/"):
            prefix = pat.rstrip("/")
            if path == prefix or path.startswith(prefix + "/"):
                return True
            continue
        if fnmatch.fnmatch(path, pat):
            return True
        # Also match basename-only patterns like `*.pem`
        if "/" not in pat and fnmatch.fnmatch(Path(path).name, pat):
            return True
        # `**/foo` style
        if pat.startswith("**/") and fnmatch.fnmatch(path, pat[3:]):
            return True
        if "**" in pat and fnmatch.fnmatch(path, pat):
            return True
    return False
