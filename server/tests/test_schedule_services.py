from datetime import date, datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import HTTPException
from fastf1.core import Laps
from freezegun import freeze_time

from app.archive import reader as archive_reader
from app.archive.archive import SessionArchive
from app.archive.reader import ArchiveReader
from app.archive.store import LocalBlobStore
from app.schedule import services
from app.schedule.services import _event_status
from tests.test_archive import _schedule


NOW = "2026-06-21 12:00:00"


@freeze_time(NOW)
def test_event_status_none():
    assert _event_status(None) == "unknown"


@freeze_time(NOW)
def test_event_status_future_aware():
    future = datetime(2026, 12, 1, 15, 0, tzinfo=timezone.utc)
    assert _event_status(future) == "upcoming"


@freeze_time(NOW)
def test_event_status_past_aware():
    past = datetime(2024, 5, 1, 15, 0, tzinfo=timezone.utc)
    assert _event_status(past) == "completed"


@freeze_time(NOW)
def test_event_status_naive_datetime_treated_as_utc():
    naive_future = datetime(2026, 12, 1, 15, 0)
    assert _event_status(naive_future) == "upcoming"


@freeze_time(NOW)
def test_event_status_date_only_combined_at_midnight():
    assert _event_status(date(2024, 1, 1)) == "completed"


@freeze_time(NOW)
@pytest.mark.parametrize(
    "ts, expected",
    [
        (pd.Timestamp("2026-12-01 15:00:00"), "upcoming"),
        (pd.Timestamp("2024-05-01 15:00:00"), "completed"),
    ],
)
def test_event_status_pandas_timestamp(ts, expected):
    assert _event_status(ts) == expected


def _session_with_laps(drivers_and_times, car_data=True):
    """A loaded session whose laps are each driver's one lap with that time (s)."""
    drivers, times = zip(*drivers_and_times)
    laps = Laps(pd.DataFrame({
        "Driver": list(drivers),
        "LapTime": pd.to_timedelta(list(times), unit="s"),
        "IsPersonalBest": [t is not None for t in times],
    }))
    data = {"1": pd.DataFrame({"Speed": [300]})} if car_data else {}
    return SimpleNamespace(laps=laps, car_data=data, pos_data=data)


def _with_telemetry(monkeypatch, *drivers):
    monkeypatch.setattr(services, "_has_telemetry", lambda lap: lap["Driver"] in drivers)


def test_reference_lap_is_the_fastest_lap(monkeypatch):
    _with_telemetry(monkeypatch, "VER", "HAM")
    session = _session_with_laps([("HAM", 81.0), ("VER", 80.0)])
    assert services._reference_lap(session)["Driver"] == "VER"


def test_reference_lap_skips_laps_without_telemetry(monkeypatch):
    _with_telemetry(monkeypatch, "LEC")
    session = _session_with_laps([("VER", 80.0), ("HAM", 81.0), ("LEC", 82.0), ("NOR", None)])
    assert services._reference_lap(session)["Driver"] == "LEC"


def test_no_reference_lap_without_telemetry(monkeypatch):
    _with_telemetry(monkeypatch)
    assert services._reference_lap(_session_with_laps([("VER", 80.0)])) is None
    _with_telemetry(monkeypatch, "VER")
    assert services._reference_lap(_session_with_laps([("VER", 80.0)], car_data=False)) is None


def _with_layout(monkeypatch, layout):
    monkeypatch.setattr(services, "_circuit_key", lambda session: 153)
    monkeypatch.setattr(services, "get_mv_circuit_info", lambda **kwargs: layout)


def _session_at_madring():
    session = _session_with_laps([("VER", 80.0)])
    session.event = SimpleNamespace(year=2026)
    session.session_info = {"Meeting": {"Circuit": {"Key": 153, "ShortName": "Madring"}}}
    return session


def test_build_circuit_info_without_a_reference_lap(monkeypatch):
    _with_telemetry(monkeypatch)
    _with_layout(monkeypatch, SimpleNamespace())
    with pytest.raises(services.CircuitInfoUnavailable, match="car and position data") as raised:
        services.build_circuit_info(_session_at_madring())
    assert not isinstance(raised.value, services.NoCircuitLayout)


def test_build_circuit_info_without_a_layout(monkeypatch):
    _with_telemetry(monkeypatch, "VER")
    _with_layout(monkeypatch, None)
    with pytest.raises(services.NoCircuitLayout, match=r"Madring \(circuit key 153\) for 2026"):
        services.build_circuit_info(_session_at_madring())


def test_reference_lap_gives_up_after_a_few_laps(monkeypatch):
    _with_telemetry(monkeypatch, "LEC")
    monkeypatch.setattr(services, "_REFERENCE_LAP_ATTEMPTS", 2)
    session = _session_with_laps([("VER", 80.0), ("HAM", 81.0), ("LEC", 82.0)])
    assert services._reference_lap(session) is None


def _fastf1_event(round_number, name, event_format, event_date, sessions, tz="UTC+03:00"):
    row = {
        "RoundNumber": round_number,
        "Country": "Bahrain",
        "Location": "Sakhir",
        "OfficialEventName": f"FORMULA 1 {name.upper()}",
        "EventDate": pd.Timestamp(event_date),
        "EventName": name,
        "EventFormat": event_format,
    }
    for i in range(1, 6):
        session_name, start = sessions[i - 1] if i <= len(sessions) else ("None", None)
        local = pd.Timestamp(start, tz=tz) if start else pd.NaT
        row[f"Session{i}"] = session_name
        row[f"Session{i}Date"] = local
        row[f"Session{i}DateUtc"] = local.tz_convert("UTC").tz_localize(None) if start else pd.NaT
    return row


FASTF1_SCHEDULE = pd.DataFrame([
    _fastf1_event(0, "Pre-Season Testing", "testing", "2025-02-28", [
        ("Practice 1", "2025-02-26 10:00"), ("Practice 2", "2025-02-27 10:00"), ("Practice 3", "2025-02-28 10:00"),
    ]),
    _fastf1_event(0, "Pre-Season Testing", "testing", "2025-03-07", [("Practice 1", "2025-03-05 10:00")]),
    _fastf1_event(1, "Bahrain Grand Prix", "conventional", "2025-04-13", [
        ("Practice 1", "2025-04-11 14:30"), ("Practice 2", "2025-04-11 18:00"), ("Practice 3", "2025-04-12 15:30"),
        ("Qualifying", "2025-04-12 19:00"), ("Race", "2025-04-13 18:00"),
    ]),
])


@pytest.fixture
def fastf1_schedule(monkeypatch):
    calls = []

    def get_event_schedule(year, backend=None):
        calls.append((year, backend))
        return FASTF1_SCHEDULE

    monkeypatch.setattr(services.fastf1, "get_event_schedule", get_event_schedule)
    return calls


def test_fastf1_season_numbers_testing_events(fastf1_schedule):
    season = services.fastf1_season(2025, backend="fastf1")
    assert [(e.round, e.event_id) for e in season.events] == [(0, "t1"), (0, "t2"), (1, "r1")]
    assert fastf1_schedule == [(2025, "fastf1")]


def test_fastf1_season_keeps_local_start_times_and_skips_empty_sessions(fastf1_schedule):
    testing, _, race = services.fastf1_season(2025).events
    assert [s.name for s in testing.sessions] == ["Practice 1", "Practice 2", "Practice 3"]
    start = race.sessions[-1].start
    assert (race.sessions[-1].name, start.hour, start.utcoffset().total_seconds()) == ("Race", 18, 3 * 3600)
    assert race.official_name == "FORMULA 1 BAHRAIN GRAND PRIX"
    assert race.date == "2025-04-13"


@freeze_time("2025-04-12 16:00:00")
def test_schedule_and_event_from_the_stored_season(fastf1_schedule):
    season = services.fastf1_season(2025)
    events = services.get_schedule(2025, season)["events"]
    assert events[2] == {
        "round": 1,
        "identifier": "r1",
        "country": "Bahrain",
        "location": "Sakhir",
        "official_event_name": "FORMULA 1 BAHRAIN GRAND PRIX",
        "event_name": "Bahrain Grand Prix",
        "event_date_start": "2025-04-11",
        "event_date_end": "2025-04-13",
        "event_format": "conventional",
        "status": "in_progress",
    }
    assert [e["status"] for e in events] == ["completed", "completed", "in_progress"]

    event = services.get_event(2025, "r1", season)
    assert (event["name"], event["round"], event["date"]) == ("Bahrain Grand Prix", 1, "2025-04-13")
    # Local times; Qualifying ends at 20:00 local, 17:00 UTC.
    assert event["sessions"][3] == {
        "name": "Qualifying",
        "identifier": "Q",
        "date": "2025-04-12",
        "start_time": "19:00",
        "end_time": "20:00",
        "status": "in_progress",
    }
    assert [s["status"] for s in event["sessions"]] == ["completed", "completed", "completed", "in_progress", "upcoming"]


def test_event_not_in_the_season_is_not_found(fastf1_schedule):
    season = services.fastf1_season(2025)
    with pytest.raises(ValueError):
        services.get_event(2025, "r2", season)
    with pytest.raises(HTTPException):
        services.get_event(2025, "x1", season)


@pytest.fixture
def archive(tmp_path):
    archive = SessionArchive(LocalBlobStore(str(tmp_path)))
    archive_reader.configure(ArchiveReader(archive, workers=4))
    yield archive
    archive_reader.configure(None)


def test_season_is_read_from_the_archive(archive, fastf1_schedule):
    archive.put_schedule(_schedule())
    assert services.get_schedule(2025)["events"][0]["location"] == "Monza"
    assert services.get_event(2025, "r16")["location"] == "Monza"
    assert fastf1_schedule == []


def test_season_not_archived_comes_from_fastf1(archive, fastf1_schedule):
    assert services.get_schedule(2025)["events"][2]["location"] == "Sakhir"
    assert fastf1_schedule == [(2025, None)]
