import threading

import pytest
from botocore.exceptions import EndpointConnectionError

from app.archive.archive import SessionArchive
from app.archive.models import StoredCircuit, StoredDriverLaps
from app.archive.reader import ArchiveReader, ArchiveUnavailable, _LRU
from app.archive.store import LocalBlobStore
from tests.test_archive import _lap, _session, _telemetry


class _CountingArchive(SessionArchive):
    """A local archive that counts reads, to tell cache hits from misses."""

    def __init__(self, root: str):
        super().__init__(LocalBlobStore(root))
        self.reads: list[str] = []
        self._lock = threading.Lock()

    def _get(self, key, model):
        with self._lock:
            self.reads.append(key)
        return super()._get(key, model)


@pytest.fixture
def archive(tmp_path):
    return _CountingArchive(str(tmp_path))


@pytest.fixture
def reader(archive):
    return ArchiveReader(archive, workers=4)


def _circuit() -> StoredCircuit:
    return StoredCircuit(rotation=90.0, corners=[], marshal_sectors=[], sector_distances=[1000.0, 2000.0])


def test_lru_evicts_least_recently_used():
    lru = _LRU(2)
    lru.put(("a",), 1)
    lru.put(("b",), 2)
    lru.get(("a",))
    lru.put(("c",), 3)
    assert lru.get(("a",)) == 1
    assert lru.get(("b",)) is None
    assert lru.get(("c",)) == 3


def test_lru_entries_expire(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.archive.reader.time.monotonic", lambda: now[0])
    lru = _LRU(2)
    lru.put(("a",), 1, ttl=60)
    lru.put(("b",), 2)
    now[0] += 60
    assert lru.get(("a",)) is None
    assert lru.get(("b",)) == 2


def test_session_is_cached(archive, reader):
    archive.put_session(_session())
    first = reader.session(2025, "r16", "R")
    second = reader.session(2025, "R16", "r")
    assert first is second
    assert len(archive.reads) == 1


def test_missing_session_is_not_cached(archive, reader):
    assert reader.session(2025, "r16", "R") is None
    archive.put_session(_session())
    assert reader.session(2025, "r16", "R") is not None


def test_unsettled_session_is_read_again_later(archive, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.archive.reader.time.monotonic", lambda: now[0])
    reader = ArchiveReader(archive, unsettled_ttl_seconds=600)
    archive.put_session(_session(results_final=False))
    assert not reader.session(2025, "r16", "R").results_final

    archive.put_session(_session(results_final=True))
    now[0] += 599
    assert not reader.session(2025, "r16", "R").results_final
    now[0] += 1
    assert reader.session(2025, "r16", "R").results_final


def test_final_session_does_not_expire(archive, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.archive.reader.time.monotonic", lambda: now[0])
    reader = ArchiveReader(archive, unsettled_ttl_seconds=600)
    archive.put_session(_session())
    reader.session(2025, "r16", "R")
    now[0] += 10 * 24 * 3600
    reader.session(2025, "r16", "R")
    assert len(archive.reads) == 1


def test_sessions_reads_several(archive, reader):
    archive.put_session(_session(identifier="Q"))
    archive.put_session(_session(identifier="R"))
    found = reader.sessions(2025, "r16", ["FP1", "Q", "R"])
    assert list(found) == ["FP1", "Q", "R"]
    assert found["FP1"] is None
    assert found["Q"].identifier == "Q"
    assert found["R"].identifier == "R"


def test_driver_laps_only_reads_drivers_with_laps(archive, reader):
    stored = _session(lap_drivers=["VER", "NOR"])
    for driver in stored.lap_drivers:
        archive.put_driver_laps(2025, "r16", "R", StoredDriverLaps(driver=driver, driver_number=None, laps=[_lap()]))

    laps = reader.driver_laps(stored, ["NOR", "HAM", "VER", "NOR"])

    assert list(laps) == ["NOR", "VER"]
    assert laps["VER"].driver == "VER"
    assert len(archive.reads) == 2


def test_lap_telemetry_keyed_by_driver_and_lap(archive, reader):
    archive.put_lap_telemetry(2025, "r16", "R", _telemetry("VER", 10))
    archive.put_lap_telemetry(2025, "r16", "R", _telemetry("NOR", 11))

    telemetry = reader.lap_telemetry(_session(), [("VER", 10), ("NOR", 11), ("NOR", 12)])

    assert telemetry[("VER", 10)].lap_number == 10
    assert telemetry[("NOR", 11)].driver == "NOR"
    assert telemetry[("NOR", 12)] is None


def test_circuit_is_cached(archive, reader):
    assert reader.circuit(2025, "r16") is None
    archive.put_circuit(2025, "r16", _circuit())
    assert reader.circuit(2025, "r16") == _circuit()
    reader.circuit(2025, "r16")
    assert len(archive.reads) == 2


def test_read_errors_become_archive_unavailable(archive, reader, monkeypatch):
    def _fail(key):
        raise EndpointConnectionError(endpoint_url="https://r2.example")

    monkeypatch.setattr(archive._store, "get", _fail)

    with pytest.raises(ArchiveUnavailable):
        reader.session(2025, "r16", "R")
    with pytest.raises(ArchiveUnavailable):
        reader.lap_telemetry(_session(), [("VER", 10), ("VER", 11)])
