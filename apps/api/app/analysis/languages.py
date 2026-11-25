"""Language detection from file extensions."""

from __future__ import annotations

EXTENSION_MAP: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".swift": "Swift",
    ".md": "Markdown",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
    ".sh": "Shell",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
}


def detect_language(path: str) -> str | None:
    lower = path.lower()
    for ext, lang in EXTENSION_MAP.items():
        if lower.endswith(ext):
            return lang
    return None


def summarize_languages(paths: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        lang = detect_language(path)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
