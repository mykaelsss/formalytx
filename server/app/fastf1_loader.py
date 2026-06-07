import threading

# One lock per session key. Routes run in FastAPI's threadpool (sync handlers),
# so a threading.Lock is the right primitive here — not asyncio.Lock.
_locks: dict[tuple, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(key: tuple) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = _locks[key] = threading.Lock()
        return lock


def locked_load(session, year: int, round: int, identifier, **load_kwargs):
    """Serialize concurrent loads of the *same* session to avoid a cache stampede.

    Without this, two simultaneous requests for the same session both miss the
    FastF1 disk cache and both cold-fetch + write it. Here the first request
    populates the cache while the rest wait on the key, then load from the warm
    cache. Loads of *different* sessions still run in parallel.
    """
    with _lock_for((year, round, str(identifier).upper())):
        session.load(**load_kwargs)
    return session
