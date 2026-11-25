"""Worker stub tests."""

import asyncio

from worker.main import health_ping


def test_health_ping() -> None:
    result = asyncio.run(health_ping({}))
    assert result == {"status": "ok"}
