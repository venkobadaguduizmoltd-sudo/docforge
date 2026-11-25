"""Admin shell API schemas and job listing helpers."""

from app.pipeline.job_store import JobRecord, clear_jobs, list_jobs, save_job
from app.schemas.admin import AdminSettingsOut
from app.schemas.jobs import JobListOut, JobOut


def test_admin_settings_placeholder_shape() -> None:
    settings = AdminSettingsOut(
        retention_days=90,
        feature_flags={"suggestion_mode": True, "template_studio": False},
        note="placeholder",
    )
    assert settings.retention_days == 90
    assert settings.feature_flags["suggestion_mode"] is True
    assert settings.feature_flags["template_studio"] is False


def test_list_jobs_registry_order() -> None:
    clear_jobs()
    older = JobRecord(id="job-a", job_type="generate_document", status="completed")
    older.created_at = "2026-01-01T00:00:00+00:00"
    newer = JobRecord(id="job-b", job_type="generate_document", status="queued")
    newer.created_at = "2026-01-02T00:00:00+00:00"
    save_job(older)
    save_job(newer)
    jobs = list_jobs()
    assert [j.id for j in jobs] == ["job-b", "job-a"]
    payload = JobListOut(
        jobs=[
            JobOut(
                id=j.id,
                job_type=j.job_type,
                status=j.status,
                payload=j.payload,
                result=j.result,
                error=j.error,
                commit_sha=j.commit_sha,
                created_at=j.created_at,
                updated_at=j.updated_at,
            )
            for j in jobs
        ]
    )
    assert len(payload.jobs) == 2
    clear_jobs()
