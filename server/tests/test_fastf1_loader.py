import os
import threading
import time
from collections import namedtuple

import pytest

from app import fastf1_loader


@pytest.fixture(autouse=True)
def _reset_session_cache():
    """`_session_cache` is module-global; clear it between tests so they don't
    leak state into each other."""
    fastf1_loader._session_cache.clear()
    yield
    fastf1_loader._session_cache.clear()


DiskUsage = namedtuple("DiskUsage", "total used free")


def _make_session_dir(root: str, year: str, event: str, session: str, size_bytes: int, mtime: float) -> str:
    path = os.path.join(root, year, event, session)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "data.ff1pkl"), "wb") as f:
        f.write(b"\0" * size_bytes)
    os.utime(path, (mtime, mtime))
    return path


def test_session_dirs_returns_leaf_dirs_only(tmp_path):
    root = str(tmp_path)
    _make_session_dir(root, "2024", "Bahrain", "FP1", size_bytes=10, mtime=1_000_000)
    _make_session_dir(root, "2024", "Bahrain", "R", size_bytes=20, mtime=1_000_001)
    _make_session_dir(root, "2025", "Monaco", "Q", size_bytes=30, mtime=1_000_002)

    leaves = fastf1_loader._session_dirs(root)

    assert sorted(leaves) == sorted(
        [
            os.path.join(root, "2024", "Bahrain", "FP1"),
            os.path.join(root, "2024", "Bahrain", "R"),
            os.path.join(root, "2025", "Monaco", "Q"),
        ]
    )


def test_session_dirs_missing_root_returns_empty(tmp_path):
    assert fastf1_loader._session_dirs(str(tmp_path / "does_not_exist")) == []


def test_session_dirs_skips_unreadable_subdirs(tmp_path):
    # Simulate the lost+found case — a top-level entry os.scandir can yield but
    # we can't descend into. Easiest: make a regular file at the year level so
    # _scandir_dirs filters it out via entry.is_dir().
    os.makedirs(tmp_path / "2024" / "Bahrain" / "FP1", exist_ok=True)
    (tmp_path / "lost+found").write_text("not a dir")

    leaves = fastf1_loader._session_dirs(str(tmp_path))

    assert leaves == [str(tmp_path / "2024" / "Bahrain" / "FP1")]


def test_dir_size_sums_files_recursively(tmp_path):
    leaf = tmp_path / "2024" / "Bahrain" / "R"
    leaf.mkdir(parents=True)
    (leaf / "a.bin").write_bytes(b"\0" * 100)
    (leaf / "b.bin").write_bytes(b"\0" * 250)
    nested = leaf / "nested"
    nested.mkdir()
    (nested / "c.bin").write_bytes(b"\0" * 50)

    assert fastf1_loader._dir_size(str(leaf)) == 400


def test_prune_cache_noop_when_high_water_zero(tmp_path, monkeypatch):
    path = _make_session_dir(str(tmp_path), "2024", "Bahrain", "R", 100, 1_000_000)
    monkeypatch.setattr(
        fastf1_loader.shutil, "disk_usage", lambda _: DiskUsage(total=1000, used=999, free=1)
    )

    fastf1_loader.prune_cache(str(tmp_path), high_water=0.0, low_water=0.0)

    assert os.path.isdir(path)


def test_prune_cache_noop_when_below_high_water(tmp_path, monkeypatch):
    path = _make_session_dir(str(tmp_path), "2024", "Bahrain", "R", 100, 1_000_000)
    monkeypatch.setattr(
        fastf1_loader.shutil, "disk_usage", lambda _: DiskUsage(total=1000, used=500, free=500)
    )

    fastf1_loader.prune_cache(str(tmp_path), high_water=0.85, low_water=0.70)

    assert os.path.isdir(path)


def test_prune_cache_evicts_oldest_sessions_first(tmp_path, monkeypatch):
    root = str(tmp_path)
    oldest = _make_session_dir(root, "2024", "Bahrain", "FP1", 400, mtime=1_000)
    middle = _make_session_dir(root, "2024", "Bahrain", "Q", 400, mtime=2_000)
    newest = _make_session_dir(root, "2024", "Bahrain", "R", 400, mtime=3_000)

    # used = 900 of 1000 (90%); high_water 0.85, low_water 0.50 -> need to free
    # used - low*total = 900 - 500 = 400 bytes. That's exactly the oldest dir.
    monkeypatch.setattr(
        fastf1_loader.shutil, "disk_usage", lambda _: DiskUsage(total=1000, used=900, free=100)
    )

    fastf1_loader.prune_cache(root, high_water=0.85, low_water=0.50)

    assert not os.path.isdir(oldest)
    assert os.path.isdir(middle)
    assert os.path.isdir(newest)


def test_prune_cache_evicts_multiple_until_target_met(tmp_path, monkeypatch):
    root = str(tmp_path)
    oldest = _make_session_dir(root, "2024", "Bahrain", "FP1", 200, mtime=1_000)
    middle = _make_session_dir(root, "2024", "Bahrain", "Q", 200, mtime=2_000)
    newest = _make_session_dir(root, "2024", "Bahrain", "R", 500, mtime=3_000)

    # Need to free 900 - 300 = 600 bytes. Oldest (200) + middle (200) = 400,
    # still short, so newest (500) must go too. After loop, freed=900 ≥ 600.
    monkeypatch.setattr(
        fastf1_loader.shutil, "disk_usage", lambda _: DiskUsage(total=1000, used=900, free=100)
    )

    fastf1_loader.prune_cache(root, high_water=0.85, low_water=0.30)

    assert not os.path.isdir(oldest)
    assert not os.path.isdir(middle)
    assert not os.path.isdir(newest)


def test_prune_cache_handles_disk_usage_failure(tmp_path, monkeypatch):
    path = _make_session_dir(str(tmp_path), "2024", "Bahrain", "R", 100, 1_000_000)

    def boom(_):
        raise OSError("disk_usage failed")

    monkeypatch.setattr(fastf1_loader.shutil, "disk_usage", boom)

    fastf1_loader.prune_cache(str(tmp_path), high_water=0.85, low_water=0.70)

    assert os.path.isdir(path)


class _FakeSession:
    """A stand-in for fastf1.core.Session. load() optionally blocks on a gate
    Event, tracks how many loads run concurrently, and records each call's
    kwargs so tests can assert on incremental-flag behavior."""

    def __init__(
        self,
        tracker: "_ConcurrencyTracker | None" = None,
        gate: threading.Event | None = None,
        hold: float = 0.0,
    ):
        self._tracker = tracker
        self._gate = gate
        self._hold = hold
        self.api_path = None
        self.load_calls: list[dict] = []

    def load(self, **kwargs):
        self.load_calls.append(kwargs)
        if self._tracker is not None:
            with self._tracker.lock:
                self._tracker.in_flight += 1
                self._tracker.max_concurrent = max(
                    self._tracker.max_concurrent, self._tracker.in_flight
                )
        try:
            if self._gate is not None:
                self._gate.wait(timeout=2.0)
            if self._hold:
                time.sleep(self._hold)
        finally:
            if self._tracker is not None:
                with self._tracker.lock:
                    self._tracker.in_flight -= 1


class _ConcurrencyTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.in_flight = 0
        self.max_concurrent = 0


def test_cached_locked_load_serializes_same_key():
    tracker = _ConcurrencyTracker()
    gate = threading.Event()
    s1 = _FakeSession(tracker, gate, hold=0.02)
    s2 = _FakeSession(tracker, gate, hold=0.02)

    def run(sess):
        fastf1_loader.cached_locked_load(sess, 2025, "r5", "R", laps=True)

    t1 = threading.Thread(target=run, args=(s1,))
    t2 = threading.Thread(target=run, args=(s2,))
    t1.start()
    t2.start()
    time.sleep(0.05)
    gate.set()
    t1.join(timeout=2.0)
    t2.join(timeout=2.0)

    assert not t1.is_alive() and not t2.is_alive()
    assert tracker.max_concurrent == 1


def test_cached_locked_load_runs_different_keys_in_parallel():
    tracker = _ConcurrencyTracker()
    gate = threading.Event()
    s1 = _FakeSession(tracker, gate)
    s2 = _FakeSession(tracker, gate)

    def run(sess, identifier):
        fastf1_loader.cached_locked_load(sess, 2025, "r5", identifier, laps=True)

    t1 = threading.Thread(target=run, args=(s1, "R"))
    t2 = threading.Thread(target=run, args=(s2, "Q"))
    t1.start()
    t2.start()
    time.sleep(0.05)
    gate.set()
    t1.join(timeout=2.0)
    t2.join(timeout=2.0)

    assert not t1.is_alive() and not t2.is_alive()
    assert tracker.max_concurrent == 2


def test_cached_locked_load_normalizes_identifier_case():
    """'r' and 'R' must share both lock and cache entry — otherwise casing
    bypasses stampede protection and double-loads the same session."""
    s1 = _FakeSession()
    s2 = _FakeSession()

    first = fastf1_loader.cached_locked_load(s1, 2025, "r5", "r", laps=True)
    second = fastf1_loader.cached_locked_load(s2, 2025, "r5", "R", laps=True)

    assert first is s1
    assert second is s1  # cache hit returns the originally-cached instance
    assert len(s1.load_calls) == 1
    assert s2.load_calls == []


def test_cached_locked_load_returns_cached_session_on_hit():
    """A second call with the same key must skip load() entirely and return the
    cached Session instance — that's the whole point of the cache."""
    cached = _FakeSession()
    later = _FakeSession()

    fastf1_loader.cached_locked_load(cached, 2025, "r5", "R", laps=True)
    returned = fastf1_loader.cached_locked_load(later, 2025, "r5", "R", laps=True)

    assert returned is cached
    assert len(cached.load_calls) == 1
    assert later.load_calls == []


def test_cached_locked_load_incremental_load_for_missing_flags():
    """If the cached Session was loaded with laps only and a later request asks
    for telemetry, the cached instance must be load()ed for just the missing
    flag, not rebuilt."""
    session = _FakeSession()

    fastf1_loader.cached_locked_load(
        session, 2025, "r5", "R", laps=True, telemetry=False, weather=False
    )
    fastf1_loader.cached_locked_load(
        session, 2025, "r5", "R", laps=True, telemetry=True, weather=False
    )

    assert len(session.load_calls) == 2
    # Second call should only ask for the missing flag.
    assert session.load_calls[1] == {"laps": False, "telemetry": True, "weather": False}


def test_cached_locked_load_no_extra_load_when_flags_already_satisfied():
    session = _FakeSession()

    fastf1_loader.cached_locked_load(
        session, 2025, "r5", "R", laps=True, telemetry=True
    )
    fastf1_loader.cached_locked_load(
        session, 2025, "r5", "R", laps=True, telemetry=False
    )

    assert len(session.load_calls) == 1


def test_cached_locked_load_evicts_lru_at_cap(monkeypatch):
    monkeypatch.setattr(fastf1_loader, "_SESSION_CACHE_MAX", 2)
    a = _FakeSession()
    b = _FakeSession()
    c = _FakeSession()

    fastf1_loader.cached_locked_load(a, 2025, "r1", "R", laps=True)
    fastf1_loader.cached_locked_load(b, 2025, "r2", "R", laps=True)
    fastf1_loader.cached_locked_load(c, 2025, "r3", "R", laps=True)

    assert (2025, "r1", "R") not in fastf1_loader._session_cache
    assert (2025, "r2", "R") in fastf1_loader._session_cache
    assert (2025, "r3", "R") in fastf1_loader._session_cache
