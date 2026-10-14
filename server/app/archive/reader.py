"""Reads of exported sessions for serving API requests.

Every request first needs its session's session.json, both as the proof that
the session is archived and for its drivers, so those are kept in a small
in-process cache. Copies whose results aren't final yet are re-read after a
while, to pick up the final export. Season schedules are cached the same way:
past seasons for good, and the current one re-read after a while, since its
events can still change. Laps and telemetry objects aren't cached here: each is
read once per request and Cloudflare caches the responses.
"""

import logging
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import TypeVar

from botocore.exceptions import BotoCoreError, ClientError

from app.archive.archive import SessionArchive
from app.archive.models import (
    StoredCircuit,
    StoredDriverLaps,
    StoredLapTelemetry,
    StoredSchedule,
    StoredSession,
)
from app.utils import ExpiringLRU

logger = logging.getLogger("uvicorn.error")

_T = TypeVar("_T")
_K = TypeVar("_K")


class ArchiveUnavailable(Exception):
    """The archive couldn't be read, e.g. R2 is down or unreachable."""


class ArchiveReader:
    def __init__(
        self,
        archive: SessionArchive,
        *,
        session_cache_size: int = 256,
        circuit_cache_size: int = 128,
        schedule_cache_size: int = 32,
        unsettled_ttl_seconds: float = 600,
        workers: int = 32,
    ):
        self._archive = archive
        self._sessions = ExpiringLRU(session_cache_size)
        self._circuits = ExpiringLRU(circuit_cache_size)
        self._schedules = ExpiringLRU(schedule_cache_size)
        self._unsettled_ttl = unsettled_ttl_seconds
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="archive-read")

    def _read(self, fn: Callable[..., _T], *args) -> _T:
        try:
            return fn(*args)
        except (BotoCoreError, ClientError, OSError) as exc:
            raise ArchiveUnavailable(f"Could not read the archive: {exc}") from exc

    def _read_many(self, fn: Callable[..., _T], keys: Iterable[_K]) -> dict[_K, _T]:
        keys = list(dict.fromkeys(keys))
        if len(keys) == 1:
            return {keys[0]: self._read(fn, *keys[0])}
        return dict(zip(keys, self._pool.map(lambda key: self._read(fn, *key), keys)))

    def schedule(self, year: int) -> StoredSchedule | None:
        """The season's exported schedule, or None when it isn't archived."""
        key = (year,)
        schedule = self._schedules.get(key)
        if schedule is None:
            schedule = self._read(self._archive.get_schedule, year)
            if schedule is not None:
                past = year < datetime.now(timezone.utc).year
                self._schedules.put(key, schedule, None if past else self._unsettled_ttl)
        return schedule

    def session(self, year: int, event_id: str, identifier: str) -> StoredSession | None:
        """The exported session, or None when it isn't archived."""
        key = (year, event_id.lower(), identifier.upper())
        stored = self._sessions.get(key)
        if stored is None:
            stored = self._read(self._archive.get_session, year, event_id, identifier)
            if stored is not None:
                self._sessions.put(key, stored, None if stored.results_final else self._unsettled_ttl)
        return stored

    def sessions(self, year: int, event_id: str, identifiers: Iterable[str]) -> dict[str, StoredSession | None]:
        identifiers = list(identifiers)
        found = self._pool.map(lambda identifier: self.session(year, event_id, identifier), identifiers)
        return dict(zip(identifiers, found))

    def driver_laps(
        self, session: StoredSession, drivers: Iterable[str]
    ) -> dict[str, StoredDriverLaps | None]:
        """Laps of each driver with laps in the session, keyed by driver."""
        keys = [
            (session.year, session.event_id, session.identifier, driver)
            for driver in drivers
            if driver in session.lap_drivers
        ]
        return {key[3]: laps for key, laps in self._read_many(self._archive.get_driver_laps, keys).items()}

    def lap_telemetry(
        self, session: StoredSession, laps: Iterable[tuple[str, int]]
    ) -> dict[tuple[str, int], StoredLapTelemetry | None]:
        keys = [(session.year, session.event_id, session.identifier, driver, lap) for driver, lap in laps]
        return {key[3:]: tel for key, tel in self._read_many(self._archive.get_lap_telemetry, keys).items()}

    def circuit(self, year: int, event_id: str) -> StoredCircuit | None:
        key = (year, event_id.lower())
        circuit = self._circuits.get(key)
        if circuit is None:
            circuit = self._read(self._archive.get_circuit, year, event_id)
            if circuit is not None:
                self._circuits.put(key, circuit)
        return circuit


_reader: ArchiveReader | None = None


def configure(reader: ArchiveReader | None) -> None:
    global _reader
    _reader = reader


def current() -> ArchiveReader | None:
    """The configured reader, or None when no archive is configured."""
    return _reader
