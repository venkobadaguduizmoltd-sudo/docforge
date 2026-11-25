"""Arq worker settings and Phase 1 generation tasks."""

import logging
import sys
from pathlib import Path
from typing import Any

from arq import cron
from arq.connections import RedisSettings

from worker.settings import get_worker_settings

logger = logging.getLogger("docforge.worker")

# Allow importing the API package when worker image mounts /api
_API_ROOT = Path("/api")
if _API_ROOT.exists() and str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))
else:
    local_api = Path(__file__).resolve().parents[2] / "api"
    if local_api.exists() and str(local_api) not in sys.path:
        sys.path.insert(0, str(local_api))


async def health_ping(ctx: dict[str, Any]) -> dict[str, str]:
    logger.info("health_ping executed")
    return {"status": "ok"}


async def generate_document(
    ctx: dict[str, Any], job_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Run the document generation pipeline for a queued job."""
    from app.pipeline.generate import run_generate_document
    from app.pipeline.job_store import JobRecord, get_job, save_job

    job = get_job(job_id) or JobRecord(id=job_id, job_type="generate_document", payload=payload)
    job.status = "running"
    save_job(job)
    try:
        result = await run_generate_document(job_id, payload)
        job = get_job(job_id) or job
        job.status = "completed"
        job.result = result
        job.commit_sha = result.get("commit_sha")
        save_job(job)
        return result
    except Exception as exc:
        job = get_job(job_id) or job
        job.status = "failed"
        job.error = str(exc)
        save_job(job)
        raise


async def startup(ctx: dict[str, Any]) -> None:
    logger.info("DocForge worker starting")


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("DocForge worker shutting down")


class WorkerSettings:
    functions = [health_ping, generate_document]
    cron_jobs = [cron(health_ping, hour={0}, minute={0})]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_worker_settings().redis_url)
