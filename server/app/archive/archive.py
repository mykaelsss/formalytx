"""Typed reads and writes of exported sessions on top of a BlobStore.

Key layout (gzip-compressed JSON):

    v1/{year}/schedule.json.gz
    v1/{year}/{event_id}/circuit.json.gz
    v1/{year}/{event_id}/{identifier}/session.json.gz
    v1/{year}/{event_id}/{identifier}/laps/{driver}.json.gz
    v1/{year}/{event_id}/{identifier}/telemetry/{driver}/{lap}.json.gz
"""

import gzip
import hashlib
import re
from collections.abc import Mapping
from typing import TypeVar

from pydantic import BaseModel

from app.archive.models import (
    FORMAT_VERSION,
    StoredCircuit,
    StoredDriverLaps,
    StoredLapTelemetry,
    StoredSchedule,
    StoredSession,
)
from app.archive.store import BlobStore, LocalBlobStore, R2BlobStore

_CONTENT_TYPE = "application/gzip"
_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")

_M = TypeVar("_M", bound=BaseModel)


def _segment(value) -> str:
    text = str(value)
    if not _SEGMENT.match(text):
        raise ValueError(f"Invalid archive key segment: {text!r}")
    return text


def schedule_key(year: int) -> str:
    return f"v{FORMAT_VERSION}/{int(year)}/schedule.json.gz"


def _event_prefix(year: int, event_id: str) -> str:
    return f"v{FORMAT_VERSION}/{int(year)}/{_segment(event_id.lower())}"


def _session_prefix(year: int, event_id: str, identifier: str) -> str:
    # Some older sessions are identified by name, e.g. "Sprint Shootout".
    return f"{_event_prefix(year, event_id)}/{_segment(identifier.upper().replace(' ', '_'))}"


def circuit_key(year: int, event_id: str) -> str:
    return f"{_event_prefix(year, event_id)}/circuit.json.gz"


def session_key(year: int, event_id: str, identifier: str) -> str:
    return f"{_session_prefix(year, event_id, identifier)}/session.json.gz"


def driver_laps_key(year: int, event_id: str, identifier: str, driver: str) -> str:
    return f"{_session_prefix(year, event_id, identifier)}/laps/{_segment(driver.upper())}.json.gz"


def lap_telemetry_key(year: int, event_id: str, identifier: str, driver: str, lap_number: int) -> str:
    return (
        f"{_session_prefix(year, event_id, identifier)}/telemetry/"
        f"{_segment(driver.upper())}/{int(lap_number)}.json.gz"
    )


def encode(model: BaseModel) -> bytes:
    # mtime=0 keeps the bytes identical across exports of identical data.
    return gzip.compress(model.model_dump_json().encode(), mtime=0)


def decode(data: bytes, model: type[_M]) -> _M:
    return model.model_validate_json(gzip.decompress(data))


class SessionArchive:
    def __init__(self, store: BlobStore):
        self._store = store

    def _get(self, key: str, model: type[_M]) -> _M | None:
        data = self._store.get(key)
        return None if data is None else decode(data, model)

    def _put(self, key: str, value: BaseModel, unless: Mapping[str, str] | None) -> bool:
        """Write the object, unless `unless` (MD5 digests by key, see digests)
        shows it's stored already. Whether it was written."""
        data = encode(value)
        if unless is not None and unless.get(key) == hashlib.md5(data).hexdigest():
            return False
        self._store.put(key, data, _CONTENT_TYPE)
        return True

    def digests(self, year: int, event_id: str, identifier: str) -> dict[str, str]:
        """The MD5 digest of each stored object an export of the session writes,
        by key: its own objects and the event's circuit info."""
        return {
            **self._store.digests(_session_prefix(year, event_id, identifier) + "/"),
            **self._store.digests(circuit_key(year, event_id)),
        }

    def get_schedule(self, year: int) -> StoredSchedule | None:
        return self._get(schedule_key(year), StoredSchedule)

    def get_session(self, year: int, event_id: str, identifier: str) -> StoredSession | None:
        return self._get(session_key(year, event_id, identifier), StoredSession)

    def get_driver_laps(self, year: int, event_id: str, identifier: str, driver: str) -> StoredDriverLaps | None:
        return self._get(driver_laps_key(year, event_id, identifier, driver), StoredDriverLaps)

    def get_lap_telemetry(
        self, year: int, event_id: str, identifier: str, driver: str, lap_number: int
    ) -> StoredLapTelemetry | None:
        return self._get(lap_telemetry_key(year, event_id, identifier, driver, lap_number), StoredLapTelemetry)

    def get_circuit(self, year: int, event_id: str) -> StoredCircuit | None:
        return self._get(circuit_key(year, event_id), StoredCircuit)

    def put_schedule(self, schedule: StoredSchedule) -> bool:
        return self._put(schedule_key(schedule.year), schedule, None)

    def put_session(self, session: StoredSession, *, unless: Mapping[str, str] | None = None) -> bool:
        return self._put(session_key(session.year, session.event_id, session.identifier), session, unless)

    def put_driver_laps(self, year: int, event_id: str, identifier: str, laps: StoredDriverLaps, *, unless: Mapping[str, str] | None = None) -> bool:
        return self._put(driver_laps_key(year, event_id, identifier, laps.driver), laps, unless)

    def put_lap_telemetry(self, year: int, event_id: str, identifier: str, telemetry: StoredLapTelemetry, *, unless: Mapping[str, str] | None = None) -> bool:
        return self._put(lap_telemetry_key(year, event_id, identifier, telemetry.driver, telemetry.lap_number), telemetry, unless)

    def put_circuit(self, year: int, event_id: str, circuit: StoredCircuit, *, unless: Mapping[str, str] | None = None) -> bool:
        return self._put(circuit_key(year, event_id), circuit, unless)


def open_archive(settings) -> SessionArchive | None:
    """The archive configured in settings: R2 when a bucket is set, else a
    local directory when one is set, else None."""
    if settings.r2_bucket:
        credentials = {
            "r2_account_id": settings.r2_account_id,
            "r2_access_key_id": settings.r2_access_key_id,
            "r2_secret_access_key": settings.r2_secret_access_key.get_secret_value(),
        }
        missing = [name for name, value in credentials.items() if not value]
        if missing:
            raise ValueError(f"r2_bucket is set but {', '.join(missing)} is empty")
        return SessionArchive(
            R2BlobStore(
                credentials["r2_account_id"],
                credentials["r2_access_key_id"],
                credentials["r2_secret_access_key"],
                settings.r2_bucket,
            )
        )
    if settings.archive_local_dir:
        return SessionArchive(LocalBlobStore(settings.archive_local_dir))
    return None
