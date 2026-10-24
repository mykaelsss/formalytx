import logging
import os
import shutil
import threading
import uuid

import fastf1
from fastf1.exceptions import DataNotLoadedError
from app.utils import KeyLockRegistry
from requests.adapters import BaseAdapter

logger = logging.getLogger("uvicorn.error")

_session_locks = KeyLockRegistry()

_active_cache_dir: str | None = None
_prune_wake: threading.Event | None = None
_high_water: float = 0.0


class SessionDataUnavailable(Exception):
    """FastF1 loaded no drivers for the session: live timing has no data for it
    yet, or refused the request, since it needs an F1 TV account."""


def warn_if_no_f1_account() -> None:
    """Live timing needs an F1 TV account, which FastF1 signs in to with these
    variables. Without them it sends its requests unauthenticated, live timing
    refuses them, and every load comes back empty."""
    if not (os.environ.get("F1_USERNAME") and os.environ.get("F1_PASSWORD")):
        logger.warning("F1_USERNAME and F1_PASSWORD are not set, so FastF1 can't load any session from live timing")


def set_cache_dir(cache_dir: str) -> None:
    global _active_cache_dir
    _active_cache_dir = cache_dir


def _apply_default_timeout(adapter: BaseAdapter, default: tuple[float, float]) -> None:
    """Make the adapter use `default` as the (connect, read) timeout of requests
    that don't set one.

    FastF1 never passes a timeout, so without this an upstream that accepts the
    connection but never answers blocks the calling thread forever. The adapter
    is wrapped rather than replaced, since FastF1 mounts its own, e.g. the one
    that signs live timing requests in to the F1 account.
    """
    send = adapter.send

    def send_with_default_timeout(request, timeout=None, **kwargs):
        return send(request, timeout=default if timeout is None else timeout, **kwargs)

    adapter.send = send_with_default_timeout


def install_request_timeouts(connect: float, read: float) -> None:
    """Apply a default timeout to every adapter on FastF1's HTTP sessions.

    Call after fastf1.Cache.configure(), which creates the cached session.
    Relies on FastF1 internals, so a missing session is logged loudly rather
    than crashing startup after a FastF1 upgrade.
    """
    for name in ("_requests_session", "_requests_session_cached"):
        session = getattr(fastf1.Cache, name, None)
        if session is None:
            logger.warning("FastF1 Cache.%s not found - its requests have no timeout", name)
            continue
        for adapter in session.adapters.values():
            _apply_default_timeout(adapter, (connect, read))


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


def locked_load(session, year: int, event_id: str, identifier, **load_kwargs) -> None:
    """Load a Session under a per-key lock keyed by (year, event_id, identifier).

    Loaded sessions aren't kept: they're only needed for sessions not in the
    archive yet, and each holds a few hundred MB. The lock makes concurrent
    loads of the same session wait for the first, which fills FastF1's disk
    cache, instead of all fetching it upstream and holding it in memory at
    once. Loads of different sessions run in parallel.

    FastF1 logs a failed load instead of raising, leaving the session empty, so
    a load that found no drivers raises SessionDataUnavailable.
    """
    key = (year, event_id, str(identifier).upper())
    with _session_locks.get(key):
        session.load(**load_kwargs)
    leaf = _session_cache_dir(session)
    if leaf and os.path.isdir(leaf):
        _touch(leaf)
    _maybe_wake_pruner()
    if not _has_drivers(session):
        raise SessionDataUnavailable(f"FastF1 loaded no drivers for {year} {event_id} {identifier}")


def _has_drivers(session) -> bool:
    try:
        return len(session.drivers) > 0
    except (DataNotLoadedError, KeyError):
        return False


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
