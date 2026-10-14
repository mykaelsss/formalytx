from datetime import date, datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest
from fastf1.core import Laps
from freezegun import freeze_time

from app.schedule import services
from app.schedule.services import _event_status


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
