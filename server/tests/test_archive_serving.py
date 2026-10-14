"""Endpoints served from the session archive instead of FastF1."""

import pytest

from app.archive import reader as archive_reader
from app.archive.archive import SessionArchive
from app.archive.models import (
    StoredCircuit,
    StoredCorner,
    StoredDriver,
    StoredDriverLaps,
    StoredFastestLap,
    StoredWeather,
)
from app.archive.reader import ArchiveReader
from app.archive.store import LocalBlobStore
from app.utils import ExpiringLRU
from app.schedule import services as schedule
from app.schedule.services import CircuitInfoUnavailable, NoCircuitLayout, SessionDetailConfig
from app.sessions import services as sessions
from tests.test_archive import _lap, _session, _telemetry


def _driver(abbreviation: str, **overrides) -> StoredDriver:
    values = {name: None for name in StoredDriver.model_fields}
    values.update(
        number="1", abbreviation=abbreviation, full_name=f"{abbreviation} Driver",
        team_name="Team", team_color="3671C6",
    )
    values.update(overrides)
    return StoredDriver(**values)


@pytest.fixture
def archive(tmp_path, monkeypatch):
    archive = SessionArchive(LocalBlobStore(str(tmp_path)))
    archive_reader.configure(ArchiveReader(archive, workers=4))
    yield archive
    archive_reader.configure(None)


@pytest.fixture
def no_fastf1(monkeypatch):
    """Fail any request that would load a session through FastF1."""
    def _fail(*args, **kwargs):
        raise AssertionError("loaded through FastF1")

    for module in (sessions, schedule):
        monkeypatch.setattr(module, "resolve_session", _fail)


def test_unarchived_sessions_fall_back_to_fastf1(archive, monkeypatch):
    def _resolve(*args):
        raise LookupError("fastf1")

    monkeypatch.setattr(sessions, "resolve_event", _resolve)
    with pytest.raises(LookupError):
        sessions.get_session(2025, "r16", "R")


def test_session_info(archive, no_fastf1):
    archive.put_session(_session(drivers=[
        _driver("VER", position=1, grid_position=2, classified_position="1", status="Finished"),
        _driver("ALB"),
    ]))

    info = sessions.get_session(2025, "r16", "R")

    assert info["event_name"] == "Italian Grand Prix"
    assert info["date"] == "2025-09-07"
    assert [d["abbreviation"] for d in info["drivers"]] == ["VER", "ALB"]
    assert info["drivers"][0]["participated"] is True
    assert info["drivers"][1]["participated"] is False


def test_practice_drivers_all_participated(archive, no_fastf1):
    archive.put_session(_session(identifier="FP1", name="Practice 1", drivers=[_driver("ALB")]))
    assert sessions.get_session(2025, "r16", "FP1")["drivers"][0]["participated"] is True


def test_driver_laps(archive, no_fastf1):
    archive.put_session(_session(lap_drivers=["VER", "NOR"]))
    archive.put_driver_laps(2025, "r16", "R", StoredDriverLaps(driver="VER", driver_number="1", laps=[
        _lap(lap_number=1, lap_time=83.456, sector1=28.1, compound="SOFT", is_personal_best=True),
        _lap(lap_number=2, compound=""),
    ]))
    archive.put_driver_laps(2025, "r16", "R", StoredDriverLaps(driver="NOR", driver_number="4", laps=[]))

    laps = sessions.get_driver_laps(2025, "r16", "r", "NOR, VER,HAM")

    assert [d["abbreviation"] for d in laps] == ["NOR", "VER"]
    [segment] = laps[1]["segments"]
    assert segment["name"] == "R"
    assert segment["laps"] == [
        {"lap_number": 1, "lap_time": "1:23.456", "sector1": "0:28.100", "sector2": None,
         "sector3": None, "compound": "SOFT", "is_personal_best": True},
        {"lap_number": 2, "lap_time": None, "sector1": None, "sector2": None,
         "sector3": None, "compound": None, "is_personal_best": False},
    ]


@pytest.mark.parametrize("identifier", ["Q", "SQ"])
def test_qualifying_laps_are_split_into_parts(archive, no_fastf1, identifier):
    archive.put_session(_session(identifier=identifier, lap_drivers=["VER"]))
    archive.put_driver_laps(2025, "r16", identifier, StoredDriverLaps(driver="VER", driver_number="1", laps=[
        _lap(lap_number=1, qualifying_part=1),
        _lap(lap_number=2, qualifying_part=1),
        _lap(lap_number=3, qualifying_part=3),
    ]))

    [driver] = sessions.get_driver_laps(2025, "r16", identifier, "VER")

    assert [s["name"] for s in driver["segments"]] == ["Q1", "Q2", "Q3"]
    assert [[lap["lap_number"] for lap in s["laps"]] for s in driver["segments"]] == [[1, 2], [], [3]]


def test_lap_telemetry(archive, no_fastf1):
    archive.put_session(_session(lap_drivers=["VER"]))
    archive.put_driver_laps(2025, "r16", "R", StoredDriverLaps(driver="VER", driver_number="1", laps=[
        _lap(lap_number=10, lap_time=83.5, compound="MEDIUM", tyre_life=4),
        _lap(lap_number=11, has_telemetry=False),
    ]))
    archive.put_lap_telemetry(2025, "r16", "R", _telemetry("VER", 10))

    telemetry = sessions.get_lap_telemetry(2025, "r16", "R", "VER:10,11,12|HAM:1")

    assert len(telemetry) == 1
    lap = telemetry[0]
    assert (lap["driver"], lap["lap_number"], lap["lap_time"]) == ("VER", 10, 83.5)
    assert (lap["compound"], lap["tyre_life"]) == ("MEDIUM", 4)
    assert lap["channels"]["speed"] == [300.0, None]
    assert lap["channels"]["brake"] == [False, True]
    assert lap["channels"]["x"] == [1.5, 2.5]


def test_practice_results_rank_by_best_lap(archive, no_fastf1):
    archive.put_session(_session(identifier="FP2", name="Practice 2", drivers=[
        _driver("NOR", best_lap_time=80.2),
        _driver("ALB"),
        _driver("VER", best_lap_time=80.1),
    ]))

    results = schedule.get_results(2025, "r16", "fp2")

    assert [(r["position"], r["code"], r["time"]) for r in results] == [
        (1, "VER", "1:20.100"),
        (2, "NOR", "+0.100s"),
    ]


def test_qualifying_results(archive, no_fastf1):
    archive.put_session(_session(identifier="Q", drivers=[
        _driver("NOR", position=2, q1=80.5, q2=80.1),
        _driver("VER", position=1, q1=80.4, q2=80.0, q3=79.9),
    ]))

    results = schedule.get_results(2025, "r16", "Q")

    assert [(r["position"], r["code"], r["q1"], r["q2"], r["q3"]) for r in results] == [
        (1, "VER", "1:20.400", "1:20.000", "1:19.900"),
        (2, "NOR", "1:20.500", "1:20.100", None),
    ]


def test_qualifying_results_without_classification_rank_by_best_lap(archive, no_fastf1):
    archive.put_session(_session(identifier="SQ", drivers=[
        _driver("NOR", best_lap_time=80.5),
        _driver("VER", best_lap_time=80.4),
    ]))

    results = schedule.get_results(2025, "r16", "SQ")

    assert [(r["position"], r["code"], r["q1"]) for r in results] == [
        (1, "VER", "1:20.400"),
        (2, "NOR", "1:20.500"),
    ]


def test_race_results_and_podium(archive, no_fastf1):
    archive.put_session(_session(drivers=[
        _driver("HAM", position=3, grid_position=5, laps=53, status="Lapped", points=15.0),
        _driver("NOR", position=2, grid_position=1, laps=53, time=19.207, status="Finished", points=18.0),
        _driver("VER", position=1, grid_position=1, laps=53, time=4413.401, status="Finished", points=25.0),
        _driver("ALB", status="Did not start"),
    ]))

    results = schedule.get_results(2025, "r16", "R")
    podium = schedule.get_podium(2025, "r16")

    assert [(r["position"], r["code"], r["time"], r["status"], r["points"]) for r in results] == [
        (1, "VER", "1:13:33.401", "Finished", 25.0),
        (2, "NOR", "+19.207s", "Finished", 18.0),
        (3, "HAM", None, "Lapped", 15.0),
    ]
    assert podium == [
        {"position": 1, "code": "VER", "time": "1:13:33.401"},
        {"position": 2, "code": "NOR", "time": "+19.207s"},
        {"position": 3, "code": "HAM", "time": "Lapped"},
    ]


def test_podium_code_falls_back_to_broadcast_name_then_number():
    assert schedule._podium_code(_driver(None, broadcast_name="M VERSTAPPEN")) == "VER"
    assert schedule._podium_code(_driver(" ", number="33")) == "33"


def test_circuit_info(archive, no_fastf1):
    corner = StoredCorner(x=1.0, y=2.0, number=1, angle=90.0, distance=300.0)
    archive.put_circuit(2025, "r16", StoredCircuit(
        rotation=92.0, corners=[corner], marshal_sectors=[], sector_distances=[1000.0, 2500.0],
    ))

    assert schedule.get_circuit_info(2025, "r16") == {
        "rotation": 92.0,
        "corners": [{"x": 1.0, "y": 2.0, "number": 1, "angle": 90.0, "distance": 300.0}],
        "marshal_sectors": [],
        "sector_distances": [1000.0, 2500.0],
    }


@pytest.fixture
def live_circuits(monkeypatch):
    """The event's sessions, each loading as itself through a fake FastF1, and
    building circuit info per `built`: a dict, or an exception to raise."""
    monkeypatch.setattr(schedule, "_live_circuits", ExpiringLRU(8))
    sessions = {"FP1": "completed", "FP2": "completed", "FP3": "completed", "Q": "upcoming"}
    monkeypatch.setattr(schedule, "get_event", lambda year, event_id: {
        "sessions": [{"identifier": i, "status": status} for i, status in sessions.items()]
    })
    loaded = []
    monkeypatch.setattr(schedule, "resolve_session", lambda year, event_id, identifier: identifier)

    def _load(session, year, event_id, identifier, **kwargs):
        loaded.append(identifier)
        return identifier

    monkeypatch.setattr(schedule, "cached_locked_load", _load)
    built = {}

    def _build(identifier):
        result = built.get(identifier, CircuitInfoUnavailable(f"no telemetry in {identifier}"))
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(schedule, "build_circuit_info", _build)
    return built, loaded


def test_circuit_info_falls_back_to_the_first_session_that_builds_it(live_circuits):
    built, loaded = live_circuits
    built.update(FP2={"from": "FP2"}, FP3={"from": "FP3"})
    assert schedule.get_circuit_info(2026, "r14") == {"from": "FP2"}
    assert schedule.get_circuit_info(2026, "r14") == {"from": "FP2"}
    assert loaded == ["FP1", "FP2"]


def test_circuit_info_skips_archived_sessions(archive, live_circuits):
    built, loaded = live_circuits
    built.update(FP1={"from": "FP1"}, FP3={"from": "FP3"})
    archive.put_session(_session(event_id="r14", identifier="FP1", name="Practice 1"))
    archive.put_session(_session(event_id="r14", identifier="FP2", name="Practice 2"))
    assert schedule.get_circuit_info(2025, "r14") == {"from": "FP3"}
    assert loaded == ["FP3"]


def test_circuit_info_unavailable_is_remembered_for_a_while(live_circuits, monkeypatch):
    built, loaded = live_circuits
    now = [1000.0]
    monkeypatch.setattr("app.utils.time.monotonic", lambda: now[0])
    for _ in range(2):
        with pytest.raises(CircuitInfoUnavailable, match="No finished session of 2026 r14"):
            schedule.get_circuit_info(2026, "r14")
    assert loaded == ["FP1", "FP2", "FP3"]
    built["FP1"] = {"from": "FP1"}
    now[0] += schedule._CIRCUIT_FAILURE_TTL_SECONDS
    assert schedule.get_circuit_info(2026, "r14") == {"from": "FP1"}


def test_circuit_info_stops_without_a_layout(live_circuits):
    built, loaded = live_circuits
    built.update(FP1=NoCircuitLayout("FastF1 has no layout of Madring"), FP2={"from": "FP2"})
    with pytest.raises(NoCircuitLayout, match="Madring"):
        schedule.get_circuit_info(2026, "r14")
    assert loaded == ["FP1"]


def test_session_weather_and_fastest_lap():
    stored = _session(
        fastest_lap=StoredFastestLap(driver="VER", lap_number=40, lap_time=79.1),
        weather=StoredWeather(
            time=[0.0, 60.0, 120.0], air_temp=[20.0, None, 21.0], track_temp=[30.0, 31.0, 32.0],
            humidity=[50.0, 50.0, 50.0], pressure=[1000.0] * 3, wind_speed=[None, None, None],
            wind_direction=[0.0] * 3, rainfall=[False, None, True],
        ),
    )

    weather, fastest = schedule._session_data_from_archive(stored, SessionDetailConfig())

    assert weather == {"air_temp": 20.5, "track_temp": 31.0, "humidity": 50.0, "wind_speed": None, "rainfall": True}
    assert fastest == "1:19.100"
    assert schedule._session_data_from_archive(stored, SessionDetailConfig(weather=False, laps=False)) == (None, None)
