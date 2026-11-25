"""Generation jobs + SSE progress."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import get_settings
from app.pipeline.generate import new_job_id, run_generate_document
from app.pipeline.job_store import JobRecord, get_job, save_job
from app.pipeline.progress import subscribe_progress
from app.rbac.deps import get_current_user, get_current_user_sse
from app.schemas.jobs import GenerateJobRequest, JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _to_out(job: JobRecord) -> JobOut:
    return JobOut(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        payload=job.payload,
        result=job.result,
        error=job.error,
        commit_sha=job.commit_sha,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def _execute_job(job_id: str, payload: dict) -> None:
    job = get_job(job_id)
    if job is None:
        return
    job.status = "running"
    save_job(job)
    try:
        result = await run_generate_document(job_id, payload)
        job = get_job(job_id) or job
        job.status = "completed"
        job.result = result
        job.commit_sha = result.get("commit_sha")
        save_job(job)
    except Exception as exc:  # noqa: BLE001
        job = get_job(job_id) or job
        job.status = "failed"
        job.error = str(exc)
        save_job(job)


@router.post("/generate", response_model=JobOut)
async def create_generate_job(
    body: GenerateJobRequest,
    background: BackgroundTasks,
    _user=Depends(get_current_user),
) -> JobOut:
    settings = get_settings()
    job_id = new_job_id()
    artifact_dir = Path(settings.artifact_dir) / job_id
    payload = body.model_dump()
    payload["output_dir"] = str(artifact_dir)
    payload["cleanup"] = False
    job = JobRecord(id=job_id, job_type="generate_document", payload=payload, status="queued")
    save_job(job)

    if settings.inline_jobs:
        background.add_task(_execute_job, job_id, payload)
    else:
        # Enqueue to Arq when not inline
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await redis.enqueue_job("generate_document", job_id, payload)
            await redis.aclose()
        except Exception:
            background.add_task(_execute_job, job_id, payload)

    return _to_out(job)


@router.get("/{job_id}", response_model=JobOut)
def get_job_status(job_id: str, _user=Depends(get_current_user)) -> JobOut:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_out(job)


@router.get("/{job_id}/events")
async def job_events(job_id: str, _user=Depends(get_current_user_sse)) -> StreamingResponse:
    if get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_stream():
        async for event in subscribe_progress(job_id):
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("stage") in {"completed", "failed"}:
                break
            await asyncio.sleep(0)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{job_id}/preview")
def job_preview(job_id: str, _user=Depends(get_current_user_sse)) -> FileResponse:
    job = get_job(job_id)
    if job is None or not job.result:
        raise HTTPException(status_code=404, detail="Preview not ready")
    html_path = job.result.get("artifacts", {}).get("html")
    if not html_path or not Path(html_path).exists():
        raise HTTPException(status_code=404, detail="HTML preview missing")
    return FileResponse(html_path, media_type="text/html")


@router.get("/{job_id}/artifacts/{kind}")
def job_artifact(job_id: str, kind: str, _user=Depends(get_current_user_sse)) -> FileResponse:
    job = get_job(job_id)
    if job is None or not job.result:
        raise HTTPException(status_code=404, detail="Artifacts not ready")
    path = job.result.get("artifacts", {}).get(kind)
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail=f"Artifact {kind} missing")
    media = {
        "html": "text/html",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }.get(kind, "application/octet-stream")
    return FileResponse(path, media_type=media, filename=Path(path).name)
