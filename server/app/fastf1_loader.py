import logging
import os
import shutil
import threading
import time
import uuid

logger = logging.getLogger("uvicorn.error")

# One lock per session key. Routes run in FastAPI's threadpool (sync handlers),
# so a threading.Lock is the right primitive here — not asyncio.Lock.
_locks: dict[tuple, threading.Lock] = {}
_locks_guard = threading.Lock()

_active_cache_dir: str | None = None


def set_cache_dir(cache_dir: str) -> None:
    global _active_cache_dir
    _active_cache_dir = cache_dir


def _lock_for(key: tuple) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = _locks[key] = threading.Lock()
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


def locked_load(session, year: int, round: int, identifier, **load_kwargs):
    """Serialize concurrent loads of the *same* session to avoid a cache stampede.

    Without this, two simultaneous requests for the same session both miss the
    FastF1 disk cache and both cold-fetch + write it. Here the first request
    populates the cache while the rest wait on the key, then load from the warm
    cache. Loads of *different* sessions still run in parallel.
    """
    with _lock_for((year, round, str(identifier).upper())):
        session.load(**load_kwargs)
    # Bump the session dir's mtime so eviction treats it as recently *used*,
    # not merely recently *written* (a cache hit never rewrites the pickle).
    leaf = _session_cache_dir(session)
    if leaf and os.path.isdir(leaf):
        _touch(leaf)
    return session


def _session_dirs(cache_dir: str) -> list[str]:
    """Leaf dirs of processed session data: cache_dir/<year>/<event>/<session>."""
    dirs: list[str] = []
    if not os.path.isdir(cache_dir):
        return dirs
    for year in os.scandir(cache_dir):
        if not year.is_dir():
            continue
        for event in os.scandir(year.path):
            if not event.is_dir():
                continue
            for sess in os.scandir(event.path):
                if sess.is_dir():
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


def prune_cache(cache_dir: str, max_bytes: int, target_bytes: int) -> None:
    """Evict least-recently-used processed session dirs when over max_bytes.

    The sqlite http cache is left untouched — it's what protects us from the
    rate-limited upstream, and processed pickles can be rebuilt from it for free.
    """
    if max_bytes <= 0:
        return
    entries = []
    total = 0
    for path in _session_dirs(cache_dir):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        size = _dir_size(path)
        entries.append((mtime, size, path))
        total += size
    if total <= max_bytes:
        return

    entries.sort()  # oldest accessed first
    freed = 0
    for _mtime, size, path in entries:
        if total - freed <= target_bytes:
            break
        _evict_dir(path)
        freed += size
        logger.info("Pruned cached session %s (%d bytes)", path, size)
    logger.info(
        "Cache prune freed %d bytes (%d -> %d, cap %d)",
        freed, total, total - freed, max_bytes,
    )


def start_pruner(cache_dir: str, max_bytes: int, target_bytes: int, interval: int) -> threading.Event:
    """Run prune_cache once now, then on a background daemon timer. Returns a stop
    Event the caller can set on shutdown."""
    stop = threading.Event()

    def _run():
        while not stop.is_set():
            try:
                prune_cache(cache_dir, max_bytes, target_bytes)
            except Exception:
                logger.exception("Cache prune failed")
            stop.wait(interval)

    if max_bytes > 0 and interval > 0:
        threading.Thread(target=_run, name="cache-pruner", daemon=True).start()
    return stop
