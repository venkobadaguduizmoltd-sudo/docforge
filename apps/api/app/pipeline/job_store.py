"""In-process job registry (Phase 1). Persists alongside DB Job rows when available."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class JobRecord:
    id: str
    job_type: str
    status: str = "queued"
    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    commit_sha: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


_JOBS: dict[str, JobRecord] = {}


def save_job(job: JobRecord) -> JobRecord:
    job.updated_at = datetime.now(UTC).isoformat()
    _JOBS[job.id] = job
    return job


def get_job(job_id: str) -> JobRecord | None:
    return _JOBS.get(job_id)


def list_jobs() -> list[JobRecord]:
    return sorted(_JOBS.values(), key=lambda j: j.created_at, reverse=True)


def clear_jobs() -> None:
    _JOBS.clear()
