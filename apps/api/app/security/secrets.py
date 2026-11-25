"""Basic secret scanning and redaction before content leaves the sandbox."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Common high-signal patterns — Phase 1 baseline, not a full secret engine.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_pat", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("github_fine_grained", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("gitlab_pat", re.compile(r"glpat-[A-Za-z0-9\-_]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    (
        "generic_api_key",
        re.compile(r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9/\+=_\-]{16,}"),
    ),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("jwt_like", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]

REDACTION = "[REDACTED]"


@dataclass
class SecretFinding:
    kind: str
    excerpt: str


def scan_text(text: str) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            findings.append(SecretFinding(kind=kind, excerpt=match.group(0)[:24]))
    return findings


def redact_text(text: str) -> tuple[str, list[SecretFinding]]:
    findings = scan_text(text)
    redacted = text
    for kind, pattern in _PATTERNS:
        redacted = pattern.sub(REDACTION, redacted)
    return redacted, findings


def redact_path_tree(root_files: dict[str, str]) -> tuple[dict[str, str], list[SecretFinding]]:
    """Redact a mapping of relative path → file text."""
    out: dict[str, str] = {}
    all_findings: list[SecretFinding] = []
    for path, content in root_files.items():
        cleaned, findings = redact_text(content)
        out[path] = cleaned
        all_findings.extend(findings)
    return out, all_findings
