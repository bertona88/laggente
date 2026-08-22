from __future__ import annotations

from collections import defaultdict, deque

import pytest
from fastapi import HTTPException

from app.rate_limit import InMemoryRateLimiter
from app import rate_limit


def test_expired_rate_limit_keys_are_reclaimed(monkeypatch):
    now = 0.0
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now)
    limiter = InMemoryRateLimiter()
    limiter.check("visitor:old", limit=2, window_seconds=10)

    now = 61.0
    limiter.check("visitor:new", limit=2, window_seconds=10)

    assert "visitor:old" not in limiter._events
    assert "visitor:old" not in limiter._windows
    assert list(limiter._events) == ["visitor:new"]


def test_large_key_cardinality_forces_cleanup_before_the_periodic_sweep(monkeypatch):
    now = 0.0
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now)
    limiter = InMemoryRateLimiter()
    for index in range(10_000):
        limiter._events[f"expired:{index}"].append(-20.0)
        limiter._windows[f"expired:{index}"] = 10

    limiter.check("visitor:current", limit=2, window_seconds=10)

    assert list(limiter._events) == ["visitor:current"]


def test_capacity_rejects_new_keys_without_evicting_or_resetting_existing_limits(
    monkeypatch,
):
    now = 0.0
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now)
    limiter = InMemoryRateLimiter(max_tracked_keys=2)
    limiter.check("visitor:one", limit=2, window_seconds=60)
    limiter.check("visitor:two", limit=2, window_seconds=60)

    with pytest.raises(HTTPException) as capacity_error:
        limiter.check("visitor:overflow", limit=2, window_seconds=60)

    assert capacity_error.value.status_code == 429
    assert set(limiter._events) == {"visitor:one", "visitor:two"}
    assert "visitor:overflow" not in limiter._windows

    limiter.check("visitor:one", limit=2, window_seconds=60)
    with pytest.raises(HTTPException) as existing_key_error:
        limiter.check("visitor:one", limit=2, window_seconds=60)

    assert existing_key_error.value.status_code == 429


def test_immediate_checks_at_capacity_do_not_repeat_full_sweeps(monkeypatch):
    class ScanCountingEvents(defaultdict):
        def __init__(self):
            super().__init__(deque)
            self.full_scans = 0

        def __iter__(self):
            self.full_scans += 1
            return super().__iter__()

    now = 0.0
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now)
    limiter = InMemoryRateLimiter(max_tracked_keys=3)
    events = ScanCountingEvents()
    limiter._events = events
    for index in range(3):
        limiter.check(f"visitor:{index}", limit=4, window_seconds=60)

    with pytest.raises(HTTPException):
        limiter.check("visitor:overflow-one", limit=4, window_seconds=60)
    with pytest.raises(HTTPException):
        limiter.check("visitor:overflow-two", limit=4, window_seconds=60)

    assert len(limiter._events) == 3
    assert "visitor:overflow-one" not in limiter._events
    assert "visitor:overflow-two" not in limiter._events
    assert events.full_scans == 1
