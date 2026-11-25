"""Analyzer tests against the sample fixture repo."""

from pathlib import Path

from app.analysis.analyzer import analyze_repository

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def test_analyze_sample_repo() -> None:
    result = analyze_repository(FIXTURE)
    assert "src/app.py" in result.files
    assert result.languages.get("Python", 0) >= 1
    assert result.languages.get("JavaScript", 0) >= 1
    names = {s.name for s in result.symbols}
    assert "Greeter" in names
    assert "main" in names or "greet" in names
    blob = result.prompt_blob()
    assert "Files" in blob
