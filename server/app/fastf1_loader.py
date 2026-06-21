import logging
import os
import shutil
import threading
import time
import uuid
import weakref

logger = logging.getLogger("uvicorn.error")


class _SessionLock:
    """Plain wrapper around threading.Lock so WeakValueDictionary can track it.
    The built-in Lock doesn't support weak references."""

    def __init__(self):
        self._lock = threading.Lock()

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, *exc):
        self._lock.release()


# One lock per session key. Routes run in FastAPI's threadpool (sync handlers),
# so a threading.Lock is the right primitive here — not asyncio.Lock. Held
# weakly so entries vanish once no in-flight request references them; without
# this the dict grows by one entry per unique (year, event_id, identifier) seen.
_locks: "weakref.WeakValueDictionary[tuple, _SessionLock]" = weakref.WeakValueDictionary()
_locks_guard = threading.Lock()

_active_cache_dir: str | None = None
_prune_wake: threading.Event | None = None
_high_water: float = 0.0


def set_cache_dir(cache_dir: str) -> None:
    global _active_cache_dir
    _active_cache_dir = cache_dir


def _lock_for(key: tuple) -> _SessionLock:
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = _SessionLock()
            _locks[key] = lock
        return lock


def _session_cache_dir(session) -> str | None:
    """The on-disk leaf dir holding this session's processed .ff1pkl files.

    Mirrors FastF1's own layout: cache_dir + api_path (sans the '/static/' prefix).
    """
    api_path = getattr(session, "api_path", None)
    if not _active_cache_dir or not api_path:
        return None
    return os.path.join(_active_cache_dir, api_path[len("/static/"):])


def _touch(path: str) -> None:
    try:
        os.utime(path)
    except OSError:
        pass


def locked_load(session, year: int, event_id: str, identifier, **load_kwargs):
    """Serialize concurrent loads of the *same* session to avoid a cache stampede.

    Without this, two simultaneous requests for the same session both miss the
    FastF1 disk cache and both cold-fetch + write it. Here the first request
    populates the cache while the rest wait on the key, then load from the warm
    cache. Loads of *different* sessions still run in parallel.
    """
    with _lock_for((year, event_id, str(identifier).upper())):
        session.load(**load_kwargs)
    # Bump the session dir's mtime so eviction treats it as recently *used*,
    # not merely recently *written* (a cache hit never rewrites the pickle).
    leaf = _session_cache_dir(session)
    if leaf and os.path.isdir(leaf):
        _touch(leaf)
    _maybe_wake_pruner()
    return session


def _disk_used_fraction(cache_dir: str) -> float | None:
    try:
        usage = shutil.disk_usage(cache_dir)
    except OSError:
        return None
    if usage.total <= 0:
        return None
    return usage.used / usage.total


def _maybe_wake_pruner() -> None:
    if _prune_wake is None or _high_water <= 0 or not _active_cache_dir:
        return
    used = _disk_used_fraction(_active_cache_dir)
    if used is not None and used > _high_water:
        _prune_wake.set()


def _scandir_dirs(path: str):
    """Yield sub-directory entries of `path`, skipping any we can't read.

    A persistent-disk mount root (ext4) contains a root-owned `lost+found` we
    can't descend into; tolerate that rather than crashing the whole walk.
    """
    try:
        entries = list(os.scandir(path))
    except OSError:
        return
    for entry in entries:
        try:
            if entry.is_dir():
                yield entry
        except OSError:
            continue


def _session_dirs(cache_dir: str) -> list[str]:
    """Leaf dirs of processed session data: cache_dir/<year>/<event>/<session>."""
    dirs: list[str] = []
    if not os.path.isdir(cache_dir):
        return dirs
    for year in _scandir_dirs(cache_dir):
        for event in _scandir_dirs(year.path):
            for sess in _scandir_dirs(event.path):
                dirs.append(sess.path)
    return dirs


def _dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _evict_dir(path: str) -> None:
    """Rename-then-delete so a concurrent reader that already opened files keeps
    working (POSIX) and a reader resolving the path afterwards just sees a cache
    miss and rebuilds from the intact sqlite http cache."""
    tmp = f"{path}.evict-{uuid.uuid4().hex}"
    try:
        os.rename(path, tmp)
    except OSError:
        return
    shutil.rmtree(tmp, ignore_errors=True)


def prune_cache(cache_dir: str, high_water: float, low_water: float) -> None:
    if high_water <= 0:
        return
    try:
        usage = shutil.disk_usage(cache_dir)
    except OSError:
        return
    if usage.total <= 0:
        return
    frac = usage.used / usage.total
    if frac <= high_water:
        logger.info("cache disk %.2f used (high %.2f) - no prune", frac, high_water)
        return
    need = usage.used - int(low_water * usage.total)

    entries = []
    for path in _session_dirs(cache_dir):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        entries.append((mtime, _dir_size(path), path))

    entries.sort()
    freed = 0
    for _mtime, size, path in entries:
        if freed >= need:
            break
        _evict_dir(path)
        freed += size
        logger.info("Pruned cached session %s (%d bytes)", path, size)
    logger.info(
        "Cache prune freed %d bytes (disk %d/%d, high %.2f, low %.2f)",
        freed, usage.used, usage.total, high_water, low_water,
    )


def start_pruner(cache_dir: str, high_water: float, low_water: float, interval: int) -> threading.Event:
    global _prune_wake, _high_water
    stop = threading.Event()
    wake = threading.Event()
    _prune_wake = wake
    _high_water = high_water

    def _run():
        while not stop.is_set():
            try:
                prune_cache(cache_dir, high_water, low_water)
            except Exception:
                logger.exception("Cache prune failed")
            wake.wait(interval)
            wake.clear()

    if high_water > 0 and interval > 0:
        threading.Thread(target=_run, name="cache-pruner", daemon=True).start()
    return stop
