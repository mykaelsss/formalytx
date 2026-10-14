import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import requests
from fastf1.exceptions import DataNotLoadedError
from fastf1.logger import get_logger, soft_exceptions
from fastf1.utils import to_timedelta

from app.archive import export
from app.archive.export import (
    EXPORT_DELAY,
    ExportOutcome,
    IncompleteLoadError,
    _capture_load_failures,
    _cast_list,
    _float_list,
    _int,
    _missing_parts,
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


def _soft_failing_load(*args, **kwargs):
    # Stands in for a part of Session.load, which FastF1 wraps the same way.
    @soft_exceptions("telemetry data", "Failed to load telemetry data!", get_logger("core"))
    def load_telemetry():
        raise requests.ConnectionError("connection reset")

    load_telemetry()


def test_capture_load_failures_collects_errors_fastf1_swallows():
    with _capture_load_failures() as load:
        _soft_failing_load()
    assert len(load.failures) == 1
    assert "telemetry data" in load.failures[0]
    assert "connection reset" in load.failures[0]


def test_capture_load_failures_ignores_values_fastf1_skips():
    # FastF1 parses gaps as times and skips those to lapping cars.
    with _capture_load_failures() as load:
        assert to_timedelta("+1 L") is None
    assert load.failures == []


def test_capture_load_failures_ignores_other_threads():
    with _capture_load_failures() as load:
        thread = threading.Thread(target=_soft_failing_load)
        thread.start()
        thread.join()
    assert load.failures == []


@pytest.fixture
def partly_loading_session(monkeypatch):
    session = _loaded_session(load=_soft_failing_load)
    monkeypatch.setattr(export, "resolve_session", lambda *args: session)
    monkeypatch.setattr(export, "session_start_utc", lambda s: END)
    monkeypatch.setattr(export, "session_end_utc", lambda s, start: END)
    exported = []
    monkeypatch.setattr(export, "export_loaded_session", lambda *args, **kwargs: exported.append(kwargs))
    archive = SimpleNamespace(get_session=lambda *args: None)
    return archive, exported


def test_export_session_refuses_a_partly_loaded_session(partly_loading_session):
    archive, exported = partly_loading_session
    with pytest.raises(IncompleteLoadError, match="telemetry data"):
        export.export_session(archive, 2025, "r16", "R", now=END + EXPORT_DELAY)
    assert exported == []


def test_export_session_allow_incomplete_records_the_failures(partly_loading_session):
    archive, exported = partly_loading_session
    outcome = export.export_session(archive, 2025, "r16", "R", allow_incomplete=True, now=END + EXPORT_DELAY)
    assert outcome is ExportOutcome.EXPORTED
    assert len(exported[0]["load_failures"]) == 1


def _loaded_session(**overrides):
    frame = lambda: pd.DataFrame({"Time": [pd.Timedelta(0)]})
    parts = {
        "laps": pd.DataFrame({"DriverNumber": ["1", "16"]}),
        "car_data": {"1": frame(), "16": frame()},
        "pos_data": {"1": frame(), "16": frame()},
        "results": frame(),
        "weather_data": frame(),
        "race_control_messages": frame(),
    }
    parts.update(overrides)
    return SimpleNamespace(**parts)


def test_missing_parts_none_for_a_complete_session():
    assert _missing_parts(_loaded_session()) == []


def test_missing_parts_reports_empty_parts():
    session = _loaded_session(
        pos_data={}, car_data={"1": pd.DataFrame()}, weather_data=None, race_control_messages=pd.DataFrame()
    )
    assert _missing_parts(session) == [
        "car data for 2 of 2 drivers",
        "position data for 2 of 2 drivers",
        "weather",
        "race control messages",
    ]


def test_missing_parts_reports_parts_that_failed_to_load():
    class NotLoaded(SimpleNamespace):
        @property
        def results(self):
            raise DataNotLoadedError("results")

    session = NotLoaded(**vars(_loaded_session(laps=pd.DataFrame({"DriverNumber": []}))))
    assert _missing_parts(session) == ["laps", "results"]
