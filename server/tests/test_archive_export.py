from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app.archive.export import (
    EXPORT_DELAY,
    ExportOutcome,
    _cast_list,
    _float_list,
    _int,
    _seconds,
    _str,
    results_final,
    session_end_utc,
    session_start_utc,
    skip_reason,
)
from app.caching import SETTLE_BUFFER

END = datetime(2025, 9, 7, 15, 0, tzinfo=timezone.utc)


def _fake_session(name="Race", event_format="conventional"):
    event = pd.Series({
        "EventFormat": event_format,
        "Session1": "Practice 1",
        "Session1DateUtc": pd.Timestamp("2025-09-05 11:30"),
        "Session5": "Race",
        "Session5DateUtc": pd.Timestamp("2025-09-07 13:00"),
    })
    return SimpleNamespace(name=name, event=event)


def test_session_start_and_end():
    session = _fake_session()
    start = session_start_utc(session)
    assert start == datetime(2025, 9, 7, 13, 0, tzinfo=timezone.utc)
    assert session_end_utc(session, start) == END


def test_testing_sessions_last_all_day():
    session = _fake_session(name="Practice 1", event_format="testing")
    start = session_start_utc(session)
    assert session_end_utc(session, start) - start == timedelta(hours=9)


def test_unknown_session_has_no_times():
    session = _fake_session(name="Sprint")
    assert session_start_utc(session) is None
    assert session_end_utc(session, None) is None


def _stored(final: bool):
    return SimpleNamespace(results_final=final)


@pytest.mark.parametrize(
    "existing, now, kwargs, expected",
    [
        # Not ready until EXPORT_DELAY after the end, unless forced.
        (None, END + EXPORT_DELAY - timedelta(minutes=1), {}, ExportOutcome.NOT_READY),
        (None, END + EXPORT_DELAY - timedelta(minutes=1), {"force": True}, None),
        (None, END + EXPORT_DELAY, {}, None),
        # Already exported and nothing new to pick up.
        (_stored(False), END + EXPORT_DELAY, {}, ExportOutcome.ALREADY_EXPORTED),
        (_stored(True), END + SETTLE_BUFFER, {}, ExportOutcome.ALREADY_EXPORTED),
        # Exported before results were final, and now they are.
        (_stored(False), END + SETTLE_BUFFER, {}, None),
        (_stored(True), END + SETTLE_BUFFER, {"overwrite": True}, None),
    ],
)
def test_skip_reason(existing, now, kwargs, expected):
    assert skip_reason(existing, END, now, **kwargs) == expected


def test_unknown_end_needs_force():
    now = END + SETTLE_BUFFER
    assert skip_reason(None, None, now) == ExportOutcome.NOT_READY
    assert skip_reason(None, None, now, force=True) is None


def test_results_final():
    assert not results_final(None, END + SETTLE_BUFFER)
    assert not results_final(END, END + SETTLE_BUFFER - timedelta(seconds=1))
    assert results_final(END, END + SETTLE_BUFFER)


@pytest.mark.parametrize("value", [None, np.nan, pd.NaT])
def test_scalars_missing(value):
    assert _seconds(value) is None
    assert _int(value) is None
    assert _str(value) is None


def test_scalars():
    assert _seconds(pd.Timedelta(minutes=1, seconds=23, milliseconds=456)) == 83.456
    assert _int(3.0) == 3
    assert _str("") == ""


def test_float_list_converts_timedeltas_and_nan():
    times = pd.Series(pd.to_timedelta([0.5, None, 1.25], unit="s"))
    assert _float_list(times) == [0.5, None, 1.25]
    assert _float_list(pd.Series([1.0, np.nan])) == [1.0, None]
    assert _float_list(pd.Series([1, 2], dtype="int64")) == [1.0, 2.0]


def test_cast_list():
    assert _cast_list(pd.Series([8, 7], dtype="int8"), int) == [8, 7]
    assert _cast_list(pd.Series([True, None], dtype="object"), bool) == [True, None]
    assert all(type(v) is int for v in _cast_list(pd.Series([8, 7], dtype="int8"), int))
