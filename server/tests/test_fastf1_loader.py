import os
import threading
import time
from collections import namedtuple

from app import fastf1_loader


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
    """A stand-in for fastf1.core.Session. load() blocks on a gate Event and
    tracks how many loads are running at the same time so tests can assert on
    serialization vs. parallelism."""

    def __init__(self, tracker: "_ConcurrencyTracker", gate: threading.Event, hold: float = 0.0):
        self._tracker = tracker
        self._gate = gate
        self._hold = hold
        self.api_path = None

    def load(self, **_kwargs):
        with self._tracker.lock:
            self._tracker.in_flight += 1
            self._tracker.max_concurrent = max(self._tracker.max_concurrent, self._tracker.in_flight)
        try:
            self._gate.wait(timeout=2.0)
            if self._hold:
                time.sleep(self._hold)
        finally:
            with self._tracker.lock:
                self._tracker.in_flight -= 1


class _ConcurrencyTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.in_flight = 0
        self.max_concurrent = 0


def test_locked_load_serializes_same_key():
    tracker = _ConcurrencyTracker()
    gate = threading.Event()
    s1 = _FakeSession(tracker, gate, hold=0.02)
    s2 = _FakeSession(tracker, gate, hold=0.02)

    def run(sess):
        fastf1_loader.locked_load(sess, 2025, "r5", "R")

    t1 = threading.Thread(target=run, args=(s1,))
    t2 = threading.Thread(target=run, args=(s2,))
    t1.start()
    t2.start()
    time.sleep(0.05)  # give t2 time to either run or block on the lock
    gate.set()
    t1.join(timeout=2.0)
    t2.join(timeout=2.0)

    assert not t1.is_alive() and not t2.is_alive()
    assert tracker.max_concurrent == 1


def test_locked_load_runs_different_keys_in_parallel():
    tracker = _ConcurrencyTracker()
    gate = threading.Event()
    s1 = _FakeSession(tracker, gate)
    s2 = _FakeSession(tracker, gate)

    def run(sess, identifier):
        fastf1_loader.locked_load(sess, 2025, "r5", identifier)

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


def test_locked_load_lock_dict_does_not_grow_unbounded():
    """After a load completes and no caller is holding the lock, its entry in
    _locks should be reclaimable — otherwise the dict grows by one per unique
    session key across the life of the process."""
    import gc

    gate = threading.Event()
    gate.set()  # let load() return immediately
    tracker = _ConcurrencyTracker()
    session = _FakeSession(tracker, gate)

    before = len(fastf1_loader._locks)
    fastf1_loader.locked_load(session, 2099, "r999", "R")
    gc.collect()
    after = len(fastf1_loader._locks)

    assert after == before, f"_locks grew from {before} to {after}; leak still present"


def test_locked_load_normalizes_identifier_case():
    """Same session at different casings must share a lock — otherwise 'r' and
    'R' bypass the stampede protection."""
    tracker = _ConcurrencyTracker()
    gate = threading.Event()
    s1 = _FakeSession(tracker, gate, hold=0.02)
    s2 = _FakeSession(tracker, gate, hold=0.02)

    def run(sess, identifier):
        fastf1_loader.locked_load(sess, 2025, "r5", identifier)

    t1 = threading.Thread(target=run, args=(s1, "r"))
    t2 = threading.Thread(target=run, args=(s2, "R"))
    t1.start()
    t2.start()
    time.sleep(0.05)
    gate.set()
    t1.join(timeout=2.0)
    t2.join(timeout=2.0)

    assert tracker.max_concurrent == 1
