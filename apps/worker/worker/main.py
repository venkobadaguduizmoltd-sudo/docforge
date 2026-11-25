"""Arq worker settings and Phase 0 stub tasks."""

import logging
from typing import Any

from arq import cron
from arq.connections import RedisSettings

from worker.settings import get_worker_settings

logger = logging.getLogger("docforge.worker")


async def health_ping(ctx: dict[str, Any]) -> dict[str, str]:
    """Lightweight job used to verify the worker can dequeue tasks."""
    logger.info("health_ping executed")
    return {"status": "ok"}


async def startup(ctx: dict[str, Any]) -> None:
    logger.info("DocForge worker starting")


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("DocForge worker shutting down")


class WorkerSettings:
    functions = [health_ping]
    cron_jobs = [cron(health_ping, hour={0}, minute={0})]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_worker_settings().redis_url)
