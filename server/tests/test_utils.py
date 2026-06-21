import gc
import threading
import time

import pytest
from fastapi import HTTPException

from app.utils import KeyLockRegistry, parse_event_id


@pytest.mark.parametrize(
    "event_id, expected",
    [
        ("t1", ("test", 1)),
        ("r5", ("race", 5)),
        ("r12", ("race", 12)),
        ("t24", ("test", 24)),
    ],
)
def test_parse_event_id_valid(event_id, expected):
    assert parse_event_id(event_id) == expected


@pytest.mark.parametrize("event_id", ["", "x3", "5", "R1", "T1"])
def test_parse_event_id_bad_prefix(event_id):
    with pytest.raises(HTTPException) as exc:
        parse_event_id(event_id)
    assert exc.value.status_code == 404


@pytest.mark.parametrize("event_id", ["r", "rabc", "t", "t1a"])
def test_parse_event_id_non_integer_number(event_id):
    with pytest.raises(HTTPException) as exc:
        parse_event_id(event_id)
    assert exc.value.status_code == 404


@pytest.mark.parametrize("event_id", ["r0", "t0", "r-1"])
def test_parse_event_id_non_positive_number(event_id):
    with pytest.raises(HTTPException) as exc:
        parse_event_id(event_id)
    assert exc.value.status_code == 404


def test_key_lock_registry_same_key_returns_same_lock():
    reg = KeyLockRegistry()
    a = reg.get((2025, "r5", "R"))
    b = reg.get((2025, "r5", "R"))
    assert a is b


def test_key_lock_registry_different_keys_return_distinct_locks():
    reg = KeyLockRegistry()
    a = reg.get((2025, "r5", "R"))
    b = reg.get((2025, "r5", "Q"))
    assert a is not b


def test_key_lock_registry_serializes_same_key():
    reg = KeyLockRegistry()
    in_flight = 0
    max_concurrent = 0
    track_lock = threading.Lock()
    gate = threading.Event()

    def worker():
        nonlocal in_flight, max_concurrent
        with reg.get(("k",)):
            with track_lock:
                in_flight += 1
                max_concurrent = max(max_concurrent, in_flight)
            gate.wait(timeout=2.0)
            time.sleep(0.02)
            with track_lock:
                in_flight -= 1

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    time.sleep(0.05)
    gate.set()
    t1.join(timeout=2.0)
    t2.join(timeout=2.0)

    assert max_concurrent == 1


def test_key_lock_registry_runs_different_keys_in_parallel():
    reg = KeyLockRegistry()
    in_flight = 0
    max_concurrent = 0
    track_lock = threading.Lock()
    gate = threading.Event()

    def worker(key):
        nonlocal in_flight, max_concurrent
        with reg.get(key):
            with track_lock:
                in_flight += 1
                max_concurrent = max(max_concurrent, in_flight)
            gate.wait(timeout=2.0)
            with track_lock:
                in_flight -= 1

    t1 = threading.Thread(target=worker, args=(("a",),))
    t2 = threading.Thread(target=worker, args=(("b",),))
    t1.start()
    t2.start()
    time.sleep(0.05)
    gate.set()
    t1.join(timeout=2.0)
    t2.join(timeout=2.0)

    assert max_concurrent == 2


def test_key_lock_registry_does_not_grow_unbounded():
    """Weak references should let lock entries drop once no caller holds them,
    otherwise the registry grows by one per unique key across the process."""
    reg = KeyLockRegistry()
    before = len(reg._locks)
    with reg.get(("ephemeral",)):
        pass
    gc.collect()
    assert len(reg._locks) == before
