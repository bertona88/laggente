from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """Small-pilot abuse limit; safe per process and replaceable without API changes."""

    def __init__(
        self,
        *,
        max_tracked_keys: int = 10_000,
        sweep_interval_seconds: float = 60.0,
    ):
        if max_tracked_keys < 1:
            raise ValueError("max_tracked_keys must be positive")
        if sweep_interval_seconds <= 0:
            raise ValueError("sweep_interval_seconds must be positive")
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._windows: dict[str, int] = {}
        self._max_tracked_keys = max_tracked_keys
        self._sweep_interval_seconds = sweep_interval_seconds
        self._last_sweep: float | None = None
        self._lock = threading.Lock()

    def _sweep_expired_keys(self, now: float) -> None:
        if (
            self._last_sweep is not None
            and now - self._last_sweep < self._sweep_interval_seconds
        ):
            return
        for candidate in list(self._events):
            events = self._events[candidate]
            cutoff = now - self._windows.get(candidate, 0)
            while events and events[0] <= cutoff:
                events.popleft()
            if not events:
                del self._events[candidate]
                self._windows.pop(candidate, None)
        self._last_sweep = now

    def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            self._sweep_expired_keys(now)
            if key not in self._events and len(self._events) >= self._max_tracked_keys:
                retry_after = max(1, int(self._sweep_interval_seconds))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Troppe richieste. Riprova tra poco.",
                    headers={"Retry-After": str(retry_after)},
                )
            self._windows[key] = max(window_seconds, self._windows.get(key, 0))
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Troppe richieste. Riprova tra poco.",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)


def client_ip(request: Request) -> str:
    # Proxy headers are intentionally ignored here. nginx should pass a normalized remote address
    # only after trusted-proxy configuration; a spoofed value must not weaken tenant authorization.
    return request.client.host if request.client else "unknown"
