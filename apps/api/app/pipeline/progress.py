"""Job progress publishing for SSE (in-memory + optional Redis pub/sub)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("docforge.pipeline.progress")

_local_queues: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)
_local_history: dict[str, list[dict[str, Any]]] = defaultdict(list)


def _channel(job_id: str) -> str:
    return f"docforge:job:{job_id}:progress"


def _event(stage: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "stage": stage,
        "detail": detail or {},
        "ts": datetime.now(UTC).isoformat(),
    }


async def publish_progress(job_id: str, stage: str, detail: dict[str, Any] | None = None) -> None:
    event = _event(stage, detail)
    _local_history[job_id].append(event)
    for queue in list(_local_queues.get(job_id, [])):
        await queue.put(event)

    try:
        from redis.asyncio import from_url

        from app.core.config import get_settings

        settings = get_settings()
        redis = from_url(settings.redis_url, decode_responses=True)
        try:
            await redis.publish(_channel(job_id), json.dumps(event))
        finally:
            await redis.aclose()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Redis publish skipped: %s", exc)


async def subscribe_progress(job_id: str) -> AsyncIterator[dict[str, Any]]:
    """Yield history then live local events until completed/failed."""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    _local_queues[job_id].append(queue)
    try:
        for past in list(_local_history.get(job_id, [])):
            yield past
            if past.get("stage") in {"completed", "failed"}:
                return
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=20.0)
            except TimeoutError:
                yield _event("heartbeat", {})
                continue
            yield event
            if event.get("stage") in {"completed", "failed"}:
                return
    finally:
        if queue in _local_queues[job_id]:
            _local_queues[job_id].remove(queue)


def clear_local_progress(job_id: str | None = None) -> None:
    if job_id is None:
        _local_queues.clear()
        _local_history.clear()
    else:
        _local_queues.pop(job_id, None)
        _local_history.pop(job_id, None)
