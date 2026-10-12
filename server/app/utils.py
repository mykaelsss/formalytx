import threading
import weakref

import fastf1
import pandas as pd
from typing import Literal
from fastapi import HTTPException


# Longest a request waits on another request's work for the same key. Kept
# under Cloudflare's 100s origin timeout so the client gets a 503 it can retry
# instead of a 524.
LOCK_WAIT_SECONDS = 60.0


class LockWaitTimeout(Exception):
    """Raised when a key lock isn't released in time - usually because its
    holder is stuck on a slow or unresponsive upstream request."""


class _KeyLock:
    """Plain wrapper around threading.Lock so WeakValueDictionary can track it.
    The built-in Lock doesn't support weak references."""

    def __init__(self, key: tuple, timeout: float):
        self._lock = threading.Lock()
        self._key = key
        self._timeout = timeout

    def __enter__(self):
        if not self._lock.acquire(timeout=self._timeout):
            raise LockWaitTimeout(f"Timed out after {self._timeout:g}s waiting for {self._key!r}")
        return self

    def __exit__(self, *exc):
        self._lock.release()


class KeyLockRegistry:
    """One lock per key. Concurrent work on the same key serializes; different
    keys run in parallel. Locks are held weakly so entries disappear once no
    in-flight caller references them — the registry doesn't grow unboundedly.

    Waiting is bounded by `timeout` so one hung holder can't block every later
    request for the same key forever; waiters raise LockWaitTimeout instead."""

    def __init__(self, timeout: float = LOCK_WAIT_SECONDS):
        self._locks: "weakref.WeakValueDictionary[tuple, _KeyLock]" = weakref.WeakValueDictionary()
        self._guard = threading.Lock()
        self._timeout = timeout

    def get(self, key: tuple) -> _KeyLock:
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = _KeyLock(key, self._timeout)
                self._locks[key] = lock
            return lock


def parse_event_id(event_id: str) -> tuple[Literal["test", "race"], int]:
    if not event_id or event_id[0] not in ("t", "r"):
        raise HTTPException(status_code=404, detail=f"Invalid event id: {event_id!r}")
    try:
        number = int(event_id[1:])
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Invalid event id: {event_id!r}")
    if number < 1:
        raise HTTPException(status_code=404, detail=f"Invalid event id: {event_id!r}")
    kind: Literal["test", "race"] = "test" if event_id[0] == "t" else "race"
    return kind, number


def resolve_event(year: int, event_id: str):
    kind, number = parse_event_id(event_id)
    return fastf1.get_testing_event(year, number) if kind == "test" else fastf1.get_event(year, number)


def resolve_session(year: int, event_id: str, identifier: str):
    kind, number = parse_event_id(event_id)
    return (
        fastf1.get_testing_session(year, number, identifier) if kind == "test"
        else fastf1.get_session(year, number, identifier)
    )


def format_lap_time(td) -> str | None:
    if td is None or pd.isna(td):
        return None
    secs = pd.Timedelta(td).total_seconds()
    m = int(secs // 60)
    s = secs % 60
    return f"{m}:{s:06.3f}"