"""In-memory replay protection via delivery id + timestamp window."""

from __future__ import annotations

import time
from threading import Lock


class ReplayGuard:
    def __init__(self, *, ttl_seconds: int = 600) -> None:
        self.ttl_seconds = ttl_seconds
        self._seen: dict[str, float] = {}
        self._lock = Lock()

    def _purge(self, now: float) -> None:
        expired = [k for k, ts in self._seen.items() if now - ts > self.ttl_seconds]
        for key in expired:
            del self._seen[key]

    def check_and_remember(
        self,
        delivery_id: str,
        *,
        timestamp: float | None = None,
        now: float | None = None,
    ) -> bool:
        """
        Return True if this delivery is fresh (allowed).
        Return False if replayed or timestamp outside TTL window.
        """
        now = time.time() if now is None else now
        if not delivery_id:
            return False
        if timestamp is not None and abs(now - timestamp) > self.ttl_seconds:
            return False
        with self._lock:
            self._purge(now)
            if delivery_id in self._seen:
                return False
            self._seen[delivery_id] = now
            return True


_GUARD = ReplayGuard()


def get_replay_guard() -> ReplayGuard:
    return _GUARD


def reset_replay_guard(ttl_seconds: int = 600) -> ReplayGuard:
    global _GUARD
    _GUARD = ReplayGuard(ttl_seconds=ttl_seconds)
    return _GUARD
