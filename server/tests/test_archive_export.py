import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import fastf1
import numpy as np
import pandas as pd
import pytest
import requests
from fastf1.exceptions import DataNotLoadedError
from fastf1.logger import get_logger, soft_exceptions
from fastf1.utils import to_timedelta

from app.archive import export
from app.archive.archive import SessionArchive
from app.archive.store import LocalBlobStore
from app.archive.export import (
    UPLOAD_WINDOW,
    ExportOutcome,
    IncompleteLoadError,
    _capture_load_failures,
    _cast_list,
    _float_list,
    _int,
    _missing_parts,
    _seconds,
    _str,
    export_schedule,
    results_final,
    session_end_utc,
    session_start_utc,
    skip_reason,
)
from app.archive.models import StoredEvent, StoredScheduleSession
from app.caching import SETTLE_BUFFER
from app.schedule.services import CircuitInfoUnavailable, NoCircuitLayout
from tests.test_archive import _schedule, _schedule_event

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
        # Not ready until it has ended, unless forced.
        (None, END - timedelta(minutes=1), {}, ExportOutcome.NOT_READY),
        (None, END - timedelta(minutes=1), {"force": True}, None),
        (None, END, {}, None),
        # Checked again until its results are final, and once they are.
        (_stored(False), END + timedelta(minutes=30), {}, None),
        (_stored(False), END + SETTLE_BUFFER, {}, None),
        # Final results don't change any more.
        (_stored(True), END + SETTLE_BUFFER, {}, ExportOutcome.ALREADY_EXPORTED),
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

    def _export(*args, **kwargs):
        exported.append(kwargs)
        return ExportOutcome.EXPORTED

    monkeypatch.setattr(export, "export_loaded_session", _export)
    archive = SimpleNamespace(get_session=lambda *args: None)
    return archive, exported


def test_export_session_refuses_a_partly_loaded_session(partly_loading_session):
    archive, exported = partly_loading_session
    with pytest.raises(IncompleteLoadError, match="telemetry data"):
        export.export_session(archive, 2025, "r16", "R", now=END + UPLOAD_WINDOW)
    assert exported == []


def test_export_session_waits_for_a_session_still_uploading(partly_loading_session):
    archive, exported = partly_loading_session
    now = END + UPLOAD_WINDOW - timedelta(minutes=1)
    assert export.export_session(archive, 2025, "r16", "R", now=now) is ExportOutcome.NOT_READY
    assert exported == []


def test_export_session_skips_a_session_without_laps(partly_loading_session, monkeypatch):
    archive, exported = partly_loading_session
    cancelled = _loaded_session(laps=pd.DataFrame({"DriverNumber": []}), load=lambda **kwargs: None)
    monkeypatch.setattr(export, "resolve_session", lambda *args: cancelled)
    early = END + UPLOAD_WINDOW - timedelta(minutes=1)
    assert export.export_session(archive, 2025, "r16", "R", now=early) is ExportOutcome.NOT_READY
    assert export.export_session(archive, 2025, "r16", "R", now=END + UPLOAD_WINDOW) is ExportOutcome.NO_DATA
    # Nothing is archived for it once its results are final either.
    final = END + SETTLE_BUFFER
    outcome = export.export_session(archive, 2025, "r16", "R", allow_incomplete_when_final=True, now=final)
    assert outcome is ExportOutcome.NO_DATA
    assert exported == []


def test_export_session_allow_incomplete_records_the_failures(partly_loading_session):
    archive, exported = partly_loading_session
    outcome = export.export_session(archive, 2025, "r16", "R", allow_incomplete=True, now=END + UPLOAD_WINDOW)
    assert outcome is ExportOutcome.EXPORTED
    assert len(exported[0]["load_failures"]) == 1


def test_export_session_allow_incomplete_when_final_waits_for_final_results(partly_loading_session):
    archive, exported = partly_loading_session
    with pytest.raises(IncompleteLoadError):
        export.export_session(archive, 2025, "r16", "R", allow_incomplete_when_final=True, now=END + UPLOAD_WINDOW)
    assert exported == []

    outcome = export.export_session(archive, 2025, "r16", "R", allow_incomplete_when_final=True, now=END + SETTLE_BUFFER)
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


class _CircuitArchive:
    def __init__(self, circuit=None):
        self.circuit = circuit

    def get_circuit(self, year, event_id):
        return self.circuit

    def put_circuit(self, year, event_id, circuit):
        self.circuit = circuit


@pytest.fixture
def sessions_with_telemetry(monkeypatch):
    """Sessions load as themselves, and build circuit info only if listed."""
    loaded = []

    def resolve(year, event_id, identifier):
        return SimpleNamespace(name=identifier, load=lambda **kwargs: loaded.append(identifier))

    with_telemetry: set[str] = set()
    monkeypatch.setattr(export, "resolve_session", resolve)
    monkeypatch.setattr(export, "_build_circuit", lambda s, *args: f"from {s.name}" if s.name in with_telemetry else None)
    return with_telemetry, loaded


def test_export_circuit_from_the_first_session_with_telemetry(sessions_with_telemetry):
    with_telemetry, loaded = sessions_with_telemetry
    with_telemetry.update({"FP2", "Q"})
    archive = _CircuitArchive()
    assert export.export_circuit(archive, 2018, "r12", ["FP1", "FP2", "Q"]) is ExportOutcome.EXPORTED
    assert archive.circuit == "from FP2"
    assert loaded == ["FP1", "FP2"]


def test_export_circuit_keeps_existing_circuit_info(sessions_with_telemetry):
    with_telemetry, loaded = sessions_with_telemetry
    with_telemetry.add("FP1")
    archive = _CircuitArchive("existing")
    assert export.export_circuit(archive, 2018, "r12", ["FP1"]) is ExportOutcome.ALREADY_EXPORTED
    assert (archive.circuit, loaded) == ("existing", [])
    assert export.export_circuit(archive, 2018, "r12", ["FP1"], overwrite=True) is ExportOutcome.EXPORTED
    assert archive.circuit == "from FP1"


def test_export_circuit_stops_without_a_layout(sessions_with_telemetry, monkeypatch):
    _, loaded = sessions_with_telemetry

    def no_layout(session, *args):
        raise NoCircuitLayout("FastF1 has no layout of Madring (circuit key 153) for 2026")

    monkeypatch.setattr(export, "_build_circuit", no_layout)
    archive = _CircuitArchive()
    with pytest.raises(NoCircuitLayout, match="Madring"):
        export.export_circuit(archive, 2026, "r14", ["FP1", "FP2"])
    assert (archive.circuit, loaded) == (None, ["FP1"])


def test_export_circuit_without_telemetry(sessions_with_telemetry):
    archive = _CircuitArchive()
    with pytest.raises(CircuitInfoUnavailable, match="2018 r12 FP1, FP2"):
        export.export_circuit(archive, 2018, "r12", ["FP1", "FP2"])
    with pytest.raises(CircuitInfoUnavailable, match="no finished sessions"):
        export.export_circuit(archive, 2018, "r12", [])
    assert archive.circuit is None


@pytest.mark.parametrize("now, cached", [(END + timedelta(hours=1), False), (END + SETTLE_BUFFER, True)])
def test_export_session_bypasses_fastf1_cache_until_results_are_final(monkeypatch, now, cached):
    seen = []
    session = _loaded_session(load=lambda **kwargs: seen.append(fastf1.Cache._tmp_disabled))
    monkeypatch.setattr(export, "resolve_session", lambda *args: session)
    monkeypatch.setattr(export, "session_start_utc", lambda s: END)
    monkeypatch.setattr(export, "session_end_utc", lambda s, start: END)
    monkeypatch.setattr(export, "export_loaded_session", lambda *args, **kwargs: ExportOutcome.EXPORTED)
    archive = SimpleNamespace(get_session=lambda *args: None)
    export.export_session(archive, 2025, "r16", "R", now=now)
    assert seen == [not cached]
    assert not fastf1.Cache._tmp_disabled


@pytest.fixture
def summary_only_session(monkeypatch):
    """A session without laps, so its export is only session.json."""
    monkeypatch.setattr(export, "_stored_drivers", lambda s: [])
    monkeypatch.setattr(export, "_qualifying_parts", lambda s: {})
    monkeypatch.setattr(export, "_telemetry_loaded", lambda s: False)
    monkeypatch.setattr(export, "_stored_event", lambda s: StoredEvent(
        round=16, name="Italian Grand Prix", official_name=None, country="Italy",
        location="Monza", date="2025-09-07", format="conventional",
    ))
    monkeypatch.setattr(export, "_stored_weather", lambda s: None)
    monkeypatch.setattr(export, "session_start_utc", lambda s: END)
    monkeypatch.setattr(export, "session_end_utc", lambda s, start: END)
    return SimpleNamespace(name="Race", event=pd.Series({"Session1": "Practice 1"}), laps=None)


def test_export_again_writes_only_what_changed(tmp_path, summary_only_session):
    session = summary_only_session
    archive = SessionArchive(LocalBlobStore(str(tmp_path)))
    first = END + timedelta(hours=1)

    def export_at(now, failures=None):
        existing = archive.get_session(2025, "r16", "R")
        return export.export_loaded_session(
            archive, session, 2025, "r16", "R", now=now, existing=existing, load_failures=failures
        )

    assert export_at(first) is ExportOutcome.EXPORTED
    assert export_at(first + timedelta(hours=1)) is ExportOutcome.UNCHANGED
    assert archive.get_session(2025, "r16", "R").exported_at == first

    later = first + timedelta(hours=2)
    assert export_at(later, failures=["weather"]) is ExportOutcome.EXPORTED
    assert archive.get_session(2025, "r16", "R").exported_at == later

    # Results becoming final changes session.json too.
    final = END + SETTLE_BUFFER
    assert export_at(final, failures=["weather"]) is ExportOutcome.EXPORTED
    assert archive.get_session(2025, "r16", "R").results_final


def test_export_schedule_writes_a_new_schedule(tmp_path):
    archive = SessionArchive(LocalBlobStore(str(tmp_path)))
    assert export_schedule(archive, _schedule()) == ExportOutcome.EXPORTED
    assert archive.get_schedule(2025) == _schedule()


def test_export_schedule_skips_an_unchanged_schedule(tmp_path):
    archive = SessionArchive(LocalBlobStore(str(tmp_path)))
    export_schedule(archive, _schedule())
    later = _schedule(exported_at=datetime(2025, 9, 9, tzinfo=timezone.utc))
    assert export_schedule(archive, later) == ExportOutcome.UNCHANGED
    assert archive.get_schedule(2025).exported_at == _schedule().exported_at


@pytest.mark.parametrize("changed", [
    # The event moved to another circuit, e.g. Bahrain's Grand Prix held in Malaysia.
    _schedule_event(country="Malaysia", location="Sepang"),
    # A session moved to the same instant in another UTC offset: its local time changed.
    _schedule_event(sessions=[
        StoredScheduleSession(name="Practice 1", start=datetime(2025, 9, 5, 12, 30, tzinfo=timezone(timedelta(hours=1)))),
        *_schedule_event().sessions[1:],
    ]),
])
def test_export_schedule_writes_a_changed_schedule(tmp_path, changed):
    archive = SessionArchive(LocalBlobStore(str(tmp_path)))
    export_schedule(archive, _schedule())
    assert export_schedule(archive, _schedule(changed)) == ExportOutcome.EXPORTED
    assert archive.get_schedule(2025).events == [changed]
