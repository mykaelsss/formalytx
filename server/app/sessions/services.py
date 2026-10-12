import fastf1
import pandas as pd
from fastf1.core import Laps
import numpy as np
from fastapi import HTTPException
from app.archive import reader
from app.archive.models import StoredLap, StoredSession
from app.utils import format_lap_time, format_seconds, resolve_event, resolve_session

from app.fastf1_loader import cached_locked_load

PRACTICE_SESSION_NAMES = {"Practice 1", "Practice 2", "Practice 3", "Practice 4"}
# Identifiers whose laps are split into Q1-Q3 segments.
QUALIFYING_IDENTIFIERS = ("Q", "SQ")

IDENTIFIER_MAP = {
    "FP1": "Practice 1",
    "FP2": "Practice 2",
    "FP3": "Practice 3",
    "Q": "Qualifying",
    "S": "Sprint",
    "SQ": "Sprint Qualifying",
    "R": "Race",
}

def _get_session_date(event, identifier: str):
    session_name = IDENTIFIER_MAP.get(identifier.upper(), identifier)
    for i in range(1, 6):
        if event.get(f"Session{i}") == session_name:
            return str(event.get(f"Session{i}DateUtc"))
    return None

def _archived_session(year: int, event_id: str, identifier: str) -> StoredSession | None:
    archive = reader.current()
    return archive.session(year, event_id, identifier) if archive is not None else None


def _session_info_from_archive(stored: StoredSession) -> dict:
    is_practice = stored.name in PRACTICE_SESSION_NAMES
    return {
        "event_name": stored.event.name,
        "name": stored.name,
        "date": stored.event.date,
        "country": stored.event.country,
        "location": stored.event.location,
        "drivers": [
            {
                "number": d.number,
                "abbreviation": d.abbreviation,
                "full_name": d.full_name,
                "team_name": d.team_name,
                "team_color": d.team_color,
                "status": d.status,
                "classified_position": d.classified_position,
                "position": d.position,
                "grid_position": d.grid_position,
                "participated": is_practice or d.grid_position is not None or d.position is not None,
            }
            for d in stored.drivers
        ],
    }


def get_session(year: int, event_id: str, identifier: str):
    stored = _archived_session(year, event_id, identifier)
    if stored is not None:
        return _session_info_from_archive(stored)
    event = resolve_event(year, event_id)
    session = resolve_session(year, event_id, identifier)
    session = cached_locked_load(session, year, event_id, identifier, laps=True, telemetry=False, weather=False, messages=True)
    
    is_practice = session.name in PRACTICE_SESSION_NAMES
    
    drivers = [
        {
            "number": d["DriverNumber"],
            "abbreviation": d["Abbreviation"],
            "full_name": d["FullName"],
            "team_name": d["TeamName"],
            "team_color": d["TeamColor"],
            "status": d["Status"],
            "classified_position": d["ClassifiedPosition"],
            "position": None if pd.isna(d["Position"]) else int(d["Position"]),
            "grid_position": None if pd.isna(d["GridPosition"]) else int(d["GridPosition"]),
            "participated": True if is_practice else not pd.isna(d["GridPosition"]) or not pd.isna(d["Position"])
        }
        for d in session.results[[
            "DriverNumber", "Abbreviation", "FullName", "TeamName",
            "TeamColor", "Status", "ClassifiedPosition", "Position", "GridPosition"
        ]].to_dict("records")
    ]
    
    return {
        "event_name": event["EventName"],
        "name": session.name,
        "date": str(event["EventDate"].date()),
        "country": event["Country"],
        "location": event["Location"],
        "drivers": drivers
    }

def _compound(value) -> str | None:
    return None if pd.isna(value) else str(value) or None


def _format_laps(driver_laps: Laps | None) -> list:
    if driver_laps is None or driver_laps.empty:
        return []
    laps = []
    for _, lap in driver_laps.iterlaps():
        is_personal_best = lap.get("IsPersonalBest", False)
        laps.append({
            "lap_number": int(lap["LapNumber"]) if not pd.isna(lap.get("LapNumber")) else None,
            "lap_time": format_lap_time(lap.get("LapTime")),
            "sector1": format_lap_time(lap.get("Sector1Time")),
            "sector2": format_lap_time(lap.get("Sector2Time")),
            "sector3": format_lap_time(lap.get("Sector3Time")),
            "compound": _compound(lap.get("Compound")),
            "is_personal_best": False if pd.isna(is_personal_best) else bool(is_personal_best),
        })
    return laps


def _format_stored_laps(laps: list[StoredLap]) -> list:
    return [
        {
            "lap_number": lap.lap_number,
            "lap_time": format_seconds(lap.lap_time),
            "sector1": format_seconds(lap.sector1),
            "sector2": format_seconds(lap.sector2),
            "sector3": format_seconds(lap.sector3),
            "compound": lap.compound or None,
            "is_personal_best": lap.is_personal_best,
        }
        for lap in laps
    ]


def _driver_laps_from_archive(stored: StoredSession, abbreviations: list[str]) -> list:
    laps_by_driver = reader.current().driver_laps(stored, abbreviations)
    result = []
    for abbreviation in abbreviations:
        driver_laps = laps_by_driver.get(abbreviation)
        if driver_laps is None:
            continue
        if stored.identifier in QUALIFYING_IDENTIFIERS:
            segments = [
                {"name": f"Q{part}", "laps": _format_stored_laps([l for l in driver_laps.laps if l.qualifying_part == part])}
                for part in (1, 2, 3)
            ]
        else:
            segments = [{"name": stored.identifier, "laps": _format_stored_laps(driver_laps.laps)}]
        result.append({"abbreviation": abbreviation, "segments": segments})
    return result


def get_driver_laps(year: int, event_id: str, identifier: str, drivers: str):
    identifier = identifier.upper()
    abbreviations = [d.strip() for d in drivers.split(',')]
    stored = _archived_session(year, event_id, identifier)
    if stored is not None:
        return _driver_laps_from_archive(stored, abbreviations)
    session = resolve_session(year, event_id, identifier)
    session = cached_locked_load(session, year, event_id, identifier, laps=True, telemetry=False, weather=False, messages=False)
    driver_laps = session.laps.pick_drivers(abbreviations)
    grouped = driver_laps.groupby("Driver")
    result = []

    for abbreviation in abbreviations:
        if abbreviation not in grouped.groups:
            continue
        group = grouped.get_group(abbreviation)
        if identifier in QUALIFYING_IDENTIFIERS:
            q1, q2, q3 = group.split_qualifying_sessions()
            segments = [
                {
                    "name": "Q1",
                    "laps": _format_laps(q1)
                },
                {
                    "name": "Q2",
                    "laps": _format_laps(q2)
                },
                {
                    "name": "Q3",
                    "laps": _format_laps(q3)
                },
            ]
        else:
            segments = [{
                "name": identifier,
                "laps": _format_laps(group)
                }]
        result.append({
            "abbreviation": abbreviation,
            "segments": segments
        })
    return result

def load_session(year: int, round: int, identifier: str):
    session = fastf1.get_session(year, round, identifier)
    session.load(telemetry=False, weather=False, messages=False)

    session_date = _get_session_date(session.event, identifier)

    drivers = []
    for _, row in session.results.iterrows():
        driver_num = str(row.name)
        driver_laps = session.laps.pick_drivers(driver_num)

        laps = []
        for _, lap in driver_laps.iterrows():
            laps.append({
                "lap_number": int(lap["LapNumber"]) if not pd.isna(lap.get("LapNumber")) else None,
                "lap_time": format_lap_time(lap.get("LapTime")),
                "sector1": format_lap_time(lap.get("Sector1Time")),
                "sector2": format_lap_time(lap.get("Sector2Time")),
                "sector3": format_lap_time(lap.get("Sector3Time")),
                "compound": str(lap.get("Compound", "")) or None,
                "is_personal_best": bool(lap.get("IsPersonalBest", False)),
            })

        drivers.append({
            "code": str(row.get("Abbreviation", driver_num)),
            "full_name": str(row.get("FullName", "")),
            "team": {
                "name": str(row.get("TeamName", "")),
                "color": str(row.get("TeamColor", "")),
            },
            "laps": laps,
        })

    return {
        "event": session.event["EventName"],
        "country": session.event["Country"],
        "location": session.event["Location"],
        "round": int(session.event["RoundNumber"]),
        "session": session.name,
        "date": session_date,
        "drivers": drivers,
    }

def _parse_selected_laps(selected_laps: str) -> list[tuple[str, list[int]]]:
    """Parse 'DRIVER:lap[,lap...]|DRIVER:lap...' into (driver, [laps]) pairs.

    Raises HTTPException(400) on malformed input so a bad client query param
    doesn't surface as a 404/500.
    """
    selections: list[tuple[str, list[int]]] = []
    for entry in selected_laps.split("|"):
        entry = entry.strip()
        if not entry:
            continue
        driver, sep, lap_str = entry.partition(":")
        driver = driver.strip()
        if not sep or not driver:
            raise HTTPException(
                400,
                f"Malformed lap selection '{entry}'; expected 'DRIVER:lap[,lap...]'.",
            )
        laps: list[int] = []
        for token in lap_str.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                laps.append(int(token))
            except ValueError:
                raise HTTPException(
                    400, f"Invalid lap number '{token}' for driver '{driver}'."
                )
        if not laps:
            raise HTTPException(400, f"No lap numbers given for driver '{driver}'.")
        selections.append((driver, laps))

    if not selections:
        raise HTTPException(400, "No laps selected.")
    return selections


def _build_lap_telemetry(session, driver: str, lap_number: int) -> dict | None:
    driver_laps = session.laps.pick_drivers(driver)
    lap_rows = driver_laps[driver_laps["LapNumber"] == float(lap_number)]
    if lap_rows.empty:
        return None
    lap_row = lap_rows.iloc[0]
    car_data = lap_row.get_car_data().add_distance()
    pos_data = lap_row.get_pos_data()
    lap_time = pd.Timedelta(lap_row["LapTime"]).total_seconds() if pd.notna(lap_row["LapTime"]) else None
    return {
        "driver": driver,
        "lap_number": lap_number,
        "lap_time": lap_time,
        "compound": _compound(lap_row.get("Compound")),
        "tyre_life": int(lap_row["TyreLife"]) if pd.notna(lap_row.get("TyreLife")) else None,
        "channels": {
            "time": car_data["Time"].dt.total_seconds().tolist(),
            "speed": car_data["Speed"].tolist(),
            "throttle": car_data["Throttle"].tolist(),
            "brake": car_data["Brake"].tolist(),
            "gear": car_data["nGear"].tolist(),
            "drs": car_data["DRS"].tolist(),
            "distance": car_data["Distance"].tolist(),
            "rpm": car_data["RPM"].tolist(),
            "x": pos_data["X"].tolist(),
            "y": pos_data["Y"].tolist(),
        }
    }


def _lap_telemetry_from_archive(stored: StoredSession, selections: list[tuple[str, list[int]]]) -> list:
    archive = reader.current()
    laps_by_driver = archive.driver_laps(stored, [driver for driver, _ in selections])
    wanted: list[tuple[str, StoredLap]] = []
    for driver, lap_numbers in selections:
        driver_laps = laps_by_driver.get(driver)
        if driver_laps is None:
            continue
        by_number: dict[int, StoredLap] = {}
        for lap in driver_laps.laps:
            if lap.lap_number is not None:
                by_number.setdefault(lap.lap_number, lap)
        for lap_number in lap_numbers:
            lap = by_number.get(lap_number)
            if lap is not None and lap.has_telemetry:
                wanted.append((driver, lap))
    telemetry = archive.lap_telemetry(stored, [(driver, lap.lap_number) for driver, lap in wanted])

    result = []
    for driver, lap in wanted:
        tel = telemetry.get((driver, lap.lap_number))
        if tel is None:
            continue
        result.append({
            "driver": driver,
            "lap_number": lap.lap_number,
            "lap_time": lap.lap_time,
            "compound": lap.compound or None,
            "tyre_life": lap.tyre_life,
            "channels": {
                "time": tel.car.time,
                "speed": tel.car.speed,
                "throttle": tel.car.throttle,
                "brake": tel.car.brake,
                "gear": tel.car.gear,
                "drs": tel.car.drs,
                "distance": tel.car.distance,
                "rpm": tel.car.rpm,
                "x": tel.pos.x,
                "y": tel.pos.y,
            },
        })
    return result


def get_lap_telemetry(year: int, event_id: str, identifier: str, selected_laps: str):
    selections = _parse_selected_laps(selected_laps)
    stored = _archived_session(year, event_id, identifier)
    if stored is not None:
        return _lap_telemetry_from_archive(stored, selections)
    session = resolve_session(year, event_id, identifier)
    session = cached_locked_load(session, year, event_id, identifier, laps=True, telemetry=True, weather=False, messages=False)
    result = []
    for driver, lap_numbers in selections:
        for lap_number in lap_numbers:
            lap = _build_lap_telemetry(session, driver, lap_number)
            if lap is not None:
                result.append(lap)
    return result
