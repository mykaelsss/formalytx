import itertools
import logging

import fastf1
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from fastf1.core import Lap, Session
from fastf1.exceptions import DataNotLoadedError
from fastf1.mvapi import get_circuit_info as get_mv_circuit_info
from dataclasses import dataclass
from app.archive import reader
from app.archive.models import StoredDriver, StoredSession, StoredWeather
from app.utils import ExpiringLRU, KeyLockRegistry, format_lap_time, format_seconds, resolve_event, resolve_session

from app.fastf1_loader import cached_locked_load

logger = logging.getLogger("uvicorn.error")

PRACTICE_IDENTIFIERS = {"FP1", "FP2", "FP3"}
QUALIFYING_IDENTIFIERS = {"Q", "SQ"}

@dataclass
class SessionDetailConfig:
    weather: bool = True
    laps: bool = True

SESSION_NAME_TO_IDENTIFIER = {
    "Practice 1": "FP1",
    "Practice 2": "FP2",
    "Practice 3": "FP3",
    "Qualifying": "Q",
    "Sprint": "S",
    "Sprint Qualifying": "SQ",
    "Race": "R",
}

SESSION_DURATION_MINUTES = {
    "FP1": 60, "FP2": 60, "FP3": 60,
    "Q": 60,
    "SQ": 60,
    "S": 30,
    "R": 120,
}

def get_schedule(year: int):
    schedule = fastf1.get_event_schedule(year)
    events = []
    test_events = 1

    for _, event in schedule.iterrows():
        status = _event_status(event["EventDate"], start_date=event.get("Session1DateUtc"))
        round_num = int(event["RoundNumber"])
        event_format = event["EventFormat"]
        identifier = ''
        if event_format == "testing":
            identifier = f"t{test_events}"
            test_events += 1
        else:
            identifier = f"r{round_num}"

        events.append({
            "round": round_num,
            "identifier": identifier,
            "country": event["Country"],
            "location": event["Location"],
            "official_event_name": event['OfficialEventName'],
            "event_name": event["EventName"],
            "event_date_start": str(event["Session1DateUtc"].date()) if event.get("Session1DateUtc") is not None else str(event["EventDate"].date()),
            "event_date_end": str(event["EventDate"].date()),
            "event_format": event["EventFormat"],
            "status": status,
        })

    return {"year": year, "events": events}

def _format_race_time(secs: float, position: int) -> str:
    """The winner's total time, or everyone else's gap to the winner."""
    if position == 1:
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        s = secs % 60
        return f"{h}:{m:02d}:{s:06.3f}"
    return f"+{secs:.3f}s"


def _format_practice_time(secs: float, leader_secs: float, position: int) -> str:
    """The leader's lap time, or everyone else's gap to it."""
    if position == 1:
        m = int(secs // 60)
        s = secs % 60
        return f"{m}:{s:06.3f}"
    # Lap times are whole milliseconds; subtract those to avoid float error.
    gap = (round(secs * 1000) - round(leader_secs * 1000)) / 1000
    return f"+{gap:.3f}s"


def _archived_session(year: int, event_id: str, identifier: str) -> StoredSession | None:
    archive = reader.current()
    return archive.session(year, event_id, identifier) if archive is not None else None


def _result_row(driver: StoredDriver, position: int, **fields) -> dict:
    row = {
        "position": position,
        "code": driver.abbreviation or "",
        "full_name": driver.full_name or "",
        "team": driver.team_name or "",
        "team_color": driver.team_color or "",
        "grid": None, "laps": None, "time": None,
        "q1": None, "q2": None, "q3": None,
        "status": None, "points": 0.0,
    }
    row.update(fields)
    return row


def _by_position(stored: StoredSession) -> list[StoredDriver]:
    return sorted((d for d in stored.drivers if d.position is not None), key=lambda d: d.position)


def _by_best_lap(stored: StoredSession) -> list[StoredDriver]:
    return sorted((d for d in stored.drivers if d.best_lap_time is not None), key=lambda d: d.best_lap_time)


def _results_from_archive(stored: StoredSession, uid: str) -> list[dict]:
    if uid in PRACTICE_IDENTIFIERS:
        fastest = _by_best_lap(stored)
        return [
            _result_row(d, pos, time=_format_practice_time(d.best_lap_time, fastest[0].best_lap_time, pos))
            for pos, d in enumerate(fastest, start=1)
        ]
    if uid in QUALIFYING_IDENTIFIERS:
        ranked = _by_position(stored)
        if not ranked:
            return [
                _result_row(d, pos, q1=format_seconds(d.best_lap_time))
                for pos, d in enumerate(_by_best_lap(stored), start=1)
            ]
        return [
            _result_row(
                d, d.position, q1=format_seconds(d.q1), q2=format_seconds(d.q2), q3=format_seconds(d.q3)
            )
            for d in ranked
        ]
    return [
        _result_row(
            d,
            d.position,
            grid=d.grid_position,
            laps=d.laps,
            time=None if d.time is None else _format_race_time(d.time, d.position),
            status=d.status or "",
            points=d.points or 0.0,
        )
        for d in _by_position(stored)
    ]


def get_results(year: int, event_id: str, identifier: str):
    uid = identifier.upper()
    stored = _archived_session(year, event_id, identifier)
    if stored is not None:
        return _results_from_archive(stored, uid)
    session = resolve_session(year, event_id, identifier)
    if uid in PRACTICE_IDENTIFIERS:
        session = cached_locked_load(session, year, event_id, identifier, laps=True, telemetry=False, weather=False, messages=False)
        return _practice_results(session)
    elif uid in QUALIFYING_IDENTIFIERS:
        session = cached_locked_load(session, year, event_id, identifier, laps=True, telemetry=False, weather=False, messages=False)
        return _qualifying_results(session)
    else:
        session = cached_locked_load(session, year, event_id, identifier, laps=False, telemetry=False, weather=False, messages=False)
        return _race_results(session)


def _race_results(session: Session):
    results = session.results.copy()
    results['Position'] = pd.to_numeric(results['Position'], errors='coerce')
    results = results.dropna(subset=['Position']).sort_values('Position')

    rows = []
    for _, row in results.iterrows():
        position = int(row['Position'])
        time_val = row.get('Time')
        if time_val is not None and not pd.isna(time_val):
            time_str = _format_race_time(pd.Timedelta(time_val).total_seconds(), position)
        else:
            time_str = None

        rows.append({
            "position": position,
            "code": str(row.get('Abbreviation', '')),
            "full_name": str(row.get('FullName', '')),
            "team": str(row.get('TeamName', '')),
            "team_color": str(row.get('TeamColor', '')),
            "grid": int(row['GridPosition']) if not pd.isna(row.get('GridPosition')) else None,
            "laps": int(row['Laps']) if not pd.isna(row.get('Laps')) else None,
            "time": time_str,
            "q1": None, "q2": None, "q3": None,
            "status": str(row.get('Status', '')),
            "points": float(row['Points']) if not pd.isna(row.get('Points')) else 0.0,
        })
    return rows


def _qualifying_results(session: Session):
    results = session.results.copy()
    results['Position'] = pd.to_numeric(results['Position'], errors='coerce')
    ranked = results.dropna(subset=['Position']).sort_values('Position')

    # Fall back to lap times if results has no positions (e.g. SQ or incomplete cache)
    if ranked.empty:
        fastest = (
            session.laps
            .dropna(subset=['LapTime'])
            .groupby('DriverNumber', as_index=False)['LapTime']
            .min()
            .sort_values('LapTime')
            .reset_index(drop=True)
        )
        rows = []
        for pos, row in fastest.iterrows():
            driver_num = str(row['DriverNumber'])
            info = results.loc[driver_num] if driver_num in results.index else None
            rows.append({
                "position": pos + 1,
                "code": str(info['Abbreviation']) if info is not None else driver_num,
                "full_name": str(info['FullName']) if info is not None else '',
                "team": str(info['TeamName']) if info is not None else '',
                "team_color": str(info['TeamColor']) if info is not None else '',
                "grid": None, "laps": None, "time": None,
                "q1": format_lap_time(row['LapTime']),
                "q2": None, "q3": None,
                "status": None, "points": 0.0,
            })
        return rows

    rows = []
    for _, row in ranked.iterrows():
        rows.append({
            "position": int(row['Position']),
            "code": str(row.get('Abbreviation', '')),
            "full_name": str(row.get('FullName', '')),
            "team": str(row.get('TeamName', '')),
            "team_color": str(row.get('TeamColor', '')),
            "grid": None, "laps": None, "time": None,
            "q1": format_lap_time(row.get('Q1')),
            "q2": format_lap_time(row.get('Q2')),
            "q3": format_lap_time(row.get('Q3')),
            "status": None, "points": 0.0,
        })
    return rows


def _practice_results(session: Session):
    results = session.results
    fastest = (
        session.laps
        .dropna(subset=['LapTime'])
        .groupby('DriverNumber', as_index=False)['LapTime']
        .min()
        .sort_values('LapTime')
        .reset_index(drop=True)
    )
    leader_time = fastest.iloc[0]['LapTime'] if not fastest.empty else None

    rows = []
    for pos, row in fastest.iterrows():
        driver_num = str(row['DriverNumber'])
        info = results.loc[driver_num] if driver_num in results.index else None
        position = pos + 1
        time_str = _format_practice_time(
            pd.Timedelta(row['LapTime']).total_seconds(), pd.Timedelta(leader_time).total_seconds(), position
        )

        rows.append({
            "position": position,
            "code": str(info['Abbreviation']) if info is not None else driver_num,
            "full_name": str(info['FullName']) if info is not None else '',
            "team": str(info['TeamName']) if info is not None else '',
            "team_color": str(info['TeamColor']) if info is not None else '',
            "grid": None,
            "laps": None,
            "time": time_str,
            "q1": None, "q2": None, "q3": None,
            "status": None,
            "points": 0.0,
        })
    return rows

def _podium_code(driver: StoredDriver) -> str:
    """Abbreviation, else the broadcast name's surname initials, else the number."""
    if driver.abbreviation and driver.abbreviation.strip():
        return driver.abbreviation.strip()
    broadcast = (driver.broadcast_name or "").strip()
    return broadcast.split()[-1][:3].upper() if broadcast else driver.number


def _podium_from_archive(stored: StoredSession) -> list[dict]:
    return [
        {
            "position": d.position,
            "code": _podium_code(d),
            "time": _format_race_time(d.time, d.position) if d.time is not None else d.status or "",
        }
        for d in _by_position(stored)[:3]
    ]


def get_podium(year: int, event_id: str):
    stored = _archived_session(year, event_id, 'R')
    if stored is not None:
        return _podium_from_archive(stored)
    session = resolve_session(year, event_id, 'R')
    session = cached_locked_load(session, year, event_id, 'R', telemetry=False, weather=False, messages=False)
    results = session.results

    # Normalise Position to numeric — older years may have strings or floats
    results = results.copy()
    results['Position'] = pd.to_numeric(results['Position'], errors='coerce')
    results = results.dropna(subset=['Position'])
    results = results.sort_values('Position').head(3)

    podium = []
    for _, row in results.iterrows():
        position = int(row['Position'])

        # Driver code: prefer Abbreviation, fall back to BroadcastName initials or DriverNumber
        code = str(row.get('Abbreviation', '') or '').strip()
        if not code or code == 'nan':
            broadcast = str(row.get('BroadcastName', '') or '').strip()
            code = broadcast.split()[-1][:3].upper() if broadcast and broadcast != 'nan' else str(int(row.get('DriverNumber', position)))

        # Time: winner gets total race time, others get gap
        time_val = row.get('Time')
        if time_val is not None and not (isinstance(time_val, float) and pd.isna(time_val)):
            try:
                time_str = _format_race_time(pd.Timedelta(time_val).total_seconds(), position)
            except Exception:
                time_str = str(row.get('Status', ''))
        else:
            time_str = str(row.get('Status', ''))

        podium.append({"position": position, "code": code, "time": time_str})

    return podium


# Circuit info built through FastF1 for events the archive has none for, or
# why it couldn't be, so repeat requests don't load sessions again. Failures
# expire, since a finished session's data can still arrive upstream.
_CIRCUIT_FAILURE_TTL_SECONDS = 600
_live_circuits = ExpiringLRU(64)
_live_circuit_locks = KeyLockRegistry()

def get_circuit_info(year: int, event_id: str):
    """Raises CircuitInfoUnavailable when the event has none."""
    archive = reader.current()
    circuit = archive.circuit(year, event_id) if archive is not None else None
    if circuit is not None:
        return circuit.model_dump(exclude={"format_version"})
    key = (year, event_id.lower())
    with _live_circuit_locks.get(key):
        result = _live_circuits.get(key)
        if result is None:
            try:
                result = _build_event_circuit_info(year, event_id)
                _live_circuits.put(key, result)
            except CircuitInfoUnavailable as exc:
                result = exc
                _live_circuits.put(key, exc, ttl=_CIRCUIT_FAILURE_TTL_SECONDS)
    if isinstance(result, CircuitInfoUnavailable):
        # A new exception each time, since concurrent requests raise it.
        raise type(result)(*result.args)
    return result

def _build_event_circuit_info(year: int, event_id: str) -> dict:
    """Circuit info from the first finished session that builds it, as the
    export does. Archived sessions are skipped: exporting them already tried."""
    identifiers = [s["identifier"] for s in get_event(year, event_id)["sessions"] if s["status"] == "completed"]
    archive = reader.current()
    if archive is not None:
        archived = archive.sessions(year, event_id, identifiers)
        identifiers = [identifier for identifier in identifiers if archived[identifier] is None]
    for identifier in identifiers:
        session = resolve_session(year, event_id, identifier)
        session = cached_locked_load(session, year, event_id, identifier, laps=True, telemetry=True, weather=False, messages=False)
        try:
            return build_circuit_info(session)
        except NoCircuitLayout:
            raise
        except (CircuitInfoUnavailable, DataNotLoadedError) as exc:
            # DataNotLoadedError: FastF1 loaded nothing of the session at all.
            logger.info("No circuit info for %s %s from %s: %s", year, event_id, identifier, exc)
    raise CircuitInfoUnavailable(f"No finished session of {year} {event_id} has circuit info")

class CircuitInfoUnavailable(Exception):
    """The session has nothing to build the circuit info from."""

class NoCircuitLayout(CircuitInfoUnavailable):
    """FastF1 has no layout for the circuit, so no session of the event has
    circuit info, e.g. at a circuit new to MultiViewer."""

_REFERENCE_LAP_ATTEMPTS = 20

def _has_telemetry(lap: Lap) -> bool:
    """Whether the lap's merged telemetry, which placing the markers takes
    its positions from, can be built."""
    try:
        if lap.get_car_data().empty or lap.get_pos_data().empty:
            return False
        # Merging also finds the car ahead, which fails when no other car's
        # data overlaps the lap, as in some sparse older sessions.
        telemetry = lap.get_telemetry(frequency="original")
        return not telemetry[telemetry["Source"] == "pos"].empty
    except Exception:
        return False

def _reference_lap(session: Session) -> Lap | None:
    """The lap to place the circuit's markers and sectors along: the fastest
    lap with car and position data.

    FastF1 only tries the fastest lap, which in some older sessions has no
    telemetry even though most other laps do.
    """
    try:
        if not session.car_data or not session.pos_data:
            return None
        laps = session.laps
    except DataNotLoadedError:
        return None
    fastest = laps.pick_fastest()
    by_time = (lap for _, lap in laps.dropna(subset=["LapTime"]).sort_values("LapTime").iterlaps())
    candidates = itertools.chain([fastest] if fastest is not None else [], by_time)
    # Merging telemetry is slow; a session this sparse is better left to the next one.
    candidates = itertools.islice(candidates, _REFERENCE_LAP_ATTEMPTS)
    return next((lap for lap in candidates if _has_telemetry(lap)), None)

def _circuit_key(session: Session) -> int:
    # As in FastF1's Session.get_circuit_info, which only takes the fastest
    # lap as its reference, including its correction of Mugello's key.
    circuit = session.session_info["Meeting"]["Circuit"]
    if circuit["Key"] == 149 and circuit["ShortName"] == "Mugello":
        return 146
    return circuit["Key"]

def build_circuit_info(session: Session) -> dict:
    """Circuit layout from a session loaded with laps and telemetry.

    Raises CircuitInfoUnavailable when no lap has both car and position data,
    e.g. when the session's telemetry is missing upstream, and NoCircuitLayout
    when FastF1 has no layout of the circuit.
    """
    # Checked first: it's quicker than finding a reference lap, and holds for
    # every session of the event.
    circuit_key = _circuit_key(session)
    circuit_info = get_mv_circuit_info(year=session.event.year, circuit_key=circuit_key)
    if circuit_info is None:
        name = session.session_info["Meeting"]["Circuit"]["ShortName"]
        raise NoCircuitLayout(f"FastF1 has no layout of {name} (circuit key {circuit_key}) for {session.event.year}")
    reference_lap = _reference_lap(session)
    if reference_lap is None:
        raise CircuitInfoUnavailable(f"none of the fastest laps of {session} has usable car and position data")
    circuit_info.add_marker_distance(reference_lap=reference_lap)

    sector_distances = []
    try:
        s1 = reference_lap.get("Sector1Time")
        s2 = reference_lap.get("Sector2Time")
        if s1 is not None and s2 is not None and not pd.isna(s1) and not pd.isna(s2):
            tel = reference_lap.get_telemetry()
            if tel is not None and not tel.empty:
                tel_time = tel["Time"].dt.total_seconds()
                s1_secs = pd.Timedelta(s1).total_seconds()
                s2_secs = s1_secs + pd.Timedelta(s2).total_seconds()
                for t in [s1_secs, s2_secs]:
                    mask = tel_time >= t
                    if mask.any():
                        sector_distances.append(float(tel.loc[mask.idxmax(), "Distance"]))
    except Exception:
        logger.exception("Error computing sector distances")

    return {
        "rotation": circuit_info.rotation,
        "corners": circuit_info.corners[["X", "Y", "Number", "Angle", "Distance"]].rename(columns=str.lower).to_dict("records"),
        "marshal_sectors": circuit_info.marshal_sectors[["X", "Y", "Number", "Angle", "Distance"]].rename(columns=str.lower).to_dict("records"),
        "sector_distances": sector_distances,
    }

def get_event(year: int, event_id: str):
    event = resolve_event(year, event_id)
    sessions = _get_event_sessions(event)

    return {
        "round": int(event["RoundNumber"]),
        "year": year,
        "name": event["EventName"],
        "country": event["Country"],
        "location": event["Location"],
        "date": str(event["EventDate"].date()),
        "format": event["EventFormat"],
        "sessions": sessions,
    }

def get_event_detailed(year: int, event_id: str, config: SessionDetailConfig = SessionDetailConfig()):
    event = resolve_event(year, event_id)
    round_num = int(event["RoundNumber"])
    sessions = _get_event_sessions_detailed(event, year, event_id, config)

    return {
        "round": round_num,
        "year": year,
        "name": event["EventName"],
        "country": event["Country"],
        "location": event["Location"],
        "date": str(event["EventDate"].date()),
        "format": event["EventFormat"],
        "sessions": sessions,
    }

def _get_event_sessions(event):
    sessions = []
    for i in range(1, 6):
        name = event.get(f"Session{i}")
        date = event.get(f"Session{i}Date")
        if not name or str(name).strip() == "":
            continue
        if pd.isna(date):
            continue
        identifier = SESSION_NAME_TO_IDENTIFIER.get(name, name)
        start_time = str(date.time())[:5]
        duration = SESSION_DURATION_MINUTES.get(identifier, 60)
        end_dt = date + timedelta(minutes=duration)
        end_time = str(end_dt.time())[:5] if end_dt else None
        status = _event_status(end_dt, start_date=date)

        sessions.append({
            "name": name,
            "identifier": identifier,
            "date": str(date.date()),
            "start_time": start_time,
            "end_time": end_time,
            "status": status,
        })
    return sessions

def _get_event_sessions_detailed(event, year: int, event_id: str, config: SessionDetailConfig):
    sessions = []
    for i in range(1, 6):
        name = event.get(f"Session{i}")
        date = event.get(f"Session{i}Date")
        if not name or str(name).strip() == "":
            continue
        if pd.isna(date):
            continue
        identifier = SESSION_NAME_TO_IDENTIFIER.get(name, name)
        start_time = str(date.time())[:5]
        duration = SESSION_DURATION_MINUTES.get(identifier, 60)
        end_dt = date + timedelta(minutes=duration)
        end_time = str(end_dt.time())[:5] if end_dt else None
        status = _event_status(end_dt, start_date=date)
        sessions.append({
            "name": name,
            "identifier": identifier,
            "date": str(date.date()),
            "start_time": start_time,
            "end_time": end_time,
            "status": status,
            "weather": None,
            "fastest_lap": None,
        })

    completed = [s["identifier"] for s in sessions if s["status"] == "completed"]
    if completed and (config.weather or config.laps):
        archive = reader.current()
        stored = archive.sessions(year, event_id, completed) if archive is not None else {}
        for s in sessions:
            if s["identifier"] not in completed:
                continue
            if stored.get(s["identifier"]) is not None:
                s["weather"], s["fastest_lap"] = _session_data_from_archive(stored[s["identifier"]], config)
            else:
                s["weather"], s["fastest_lap"] = _get_session_data(year, event_id, s["identifier"], config)
    return sessions


def _mean(values: list[float | None]) -> float | None:
    # Same summation as the pandas mean of the FastF1 path, so both round alike.
    array = np.array([np.nan if v is None else v for v in values], dtype=float)
    return None if np.isnan(array).all() else round_val(np.nanmean(array))


def _weather_from_archive(w: StoredWeather) -> dict:
    return {
        "air_temp": _mean(w.air_temp),
        "track_temp": _mean(w.track_temp),
        "humidity": _mean(w.humidity),
        "wind_speed": _mean(w.wind_speed),
        "rainfall": any(w.rainfall),
    }


def _session_data_from_archive(stored: StoredSession, config: SessionDetailConfig):
    weather = _weather_from_archive(stored.weather) if config.weather and stored.weather is not None else None
    fastest_lap = None
    if config.laps and stored.fastest_lap is not None:
        fastest_lap = format_seconds(stored.fastest_lap.lap_time)
    return weather, fastest_lap


def _get_session_data(year: int, event_id: str, identifier: str, config: SessionDetailConfig):
    try:
        session = resolve_session(year, event_id, identifier)
        session = cached_locked_load(session, year, event_id, identifier, laps=config.laps, telemetry=False, messages=False, weather=config.weather)

        weather = None
        w = session.weather_data if config.weather else None
        if w is not None and not w.empty:
            weather = {
                "air_temp": round_val(w["AirTemp"].mean()),
                "track_temp": round_val(w["TrackTemp"].mean()),
                "humidity": round_val(w["Humidity"].mean()),
                "wind_speed": round_val(w["WindSpeed"].mean()),
                "rainfall": bool(w["Rainfall"].any()),
            }

        fastest_lap = None
        if config.laps and session.laps is not None:
            lap = session.laps.pick_fastest()
            try:
                if lap is not None:
                    fastest_lap = format_lap_time(lap.get("LapTime"))
            except Exception:
                logger.exception("Error in _get_session_data trying to format lap time")

        return weather, fastest_lap
    except Exception:
        logger.exception("Error in _get_session_data")
        return None, None

def _event_status(date, start_date=None):
    if date is None:
        return "unknown"
    now = datetime.now(timezone.utc)
    event_date = date if isinstance(date, datetime) else datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc)
    if event_date.tzinfo is None:
        event_date = event_date.replace(tzinfo=timezone.utc)
    if event_date <= now:
        return "completed"
    if start_date is not None:
        start = start_date if isinstance(start_date, datetime) else datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if start <= now:
            return "in_progress"
    return "upcoming"

def round_val(val):
    try:
        return round(float(val), 1)
    except Exception:
        return None


def _check_data_availability(year: int, round: int, identifier: str):
    try:
        session = fastf1.get_session(year, round, identifier)
        session.load(telemetry=False, weather=False, messages=False)
        laps = session.laps
        has_laps = laps is not None and not laps.empty
        has_telemetry = False
        if has_laps:
            try:
                tel = laps.iloc[0].get_telemetry()
                has_telemetry = tel is not None and not tel.empty
            except Exception:
                pass
        return {"telemetry_available": has_telemetry, "replay_available": has_telemetry}
    except Exception:
        return {"telemetry_available": False, "replay_available": False}
