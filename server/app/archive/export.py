"""Export a finished session from FastF1 into the archive."""

import enum
import logging
import threading
import time
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import fastf1
import numpy as np
import pandas as pd
from fastf1.core import Lap, Session
from fastf1.exceptions import DataNotLoadedError

from app.archive.archive import SessionArchive
from app.archive.models import (
    StoredCarData,
    StoredCircuit,
    StoredDriver,
    StoredDriverLaps,
    StoredEvent,
    StoredFastestLap,
    StoredLap,
    StoredLapTelemetry,
    StoredPosData,
    StoredSession,
    StoredWeather,
)
from app.caching import SETTLE_BUFFER
from app.schedule.services import SESSION_DURATION_MINUTES, SESSION_NAME_TO_IDENTIFIER, build_circuit_info
from app.utils import resolve_session

logger = logging.getLogger("uvicorn.error")

# FastF1 data usually appears within an hour or two of a session ending.
# Waiting longer avoids archiving a partial upload as if it were complete.
EXPORT_DELAY = timedelta(hours=6)
# Testing days run all day, not for a regular session's length.
TESTING_SESSION_MINUTES = 9 * 60
QUALIFYING_SESSION_NAMES = {"Qualifying", "Sprint Qualifying", "Sprint Shootout"}


class ExportOutcome(enum.Enum):
    EXPORTED = "exported"
    ALREADY_EXPORTED = "already exported"
    NOT_READY = "not ready"


def _utc(value) -> datetime:
    ts = pd.Timestamp(value).to_pydatetime()
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)


def session_start_utc(session: Session) -> datetime | None:
    event = session.event
    for i in range(1, 6):
        if event.get(f"Session{i}") != session.name:
            continue
        start = event.get(f"Session{i}DateUtc")
        return None if start is None or pd.isna(start) else _utc(start)
    return None


def session_end_utc(session: Session, start: datetime | None) -> datetime | None:
    if start is None:
        return None
    if session.event.get("EventFormat") == "testing":
        minutes = TESTING_SESSION_MINUTES
    else:
        minutes = SESSION_DURATION_MINUTES.get(SESSION_NAME_TO_IDENTIFIER.get(session.name, ""), 60)
    return start + timedelta(minutes=minutes)


def results_final(end: datetime | None, now: datetime) -> bool:
    return end is not None and now >= end + SETTLE_BUFFER


def skip_reason(
    existing: StoredSession | None,
    end: datetime | None,
    now: datetime,
    *,
    force: bool = False,
    overwrite: bool = False,
) -> ExportOutcome | None:
    """Why this session shouldn't be exported now, or None to export it.

    A stored copy is exported again once its results become final, so a
    session exported soon after it ended picks up later penalties.
    """
    if not force and (end is None or now < end + EXPORT_DELAY):
        return ExportOutcome.NOT_READY
    if existing is not None and not overwrite:
        if existing.results_final or not results_final(end, now):
            return ExportOutcome.ALREADY_EXPORTED
    return None


def _missing(value) -> bool:
    return value is None or (not isinstance(value, (list, tuple, np.ndarray)) and pd.isna(value))


def _seconds(value) -> float | None:
    return None if _missing(value) else pd.Timedelta(value).total_seconds()


def _float(value) -> float | None:
    return None if _missing(value) else float(value)


def _int(value) -> int | None:
    return None if _missing(value) else int(value)


def _bool(value) -> bool | None:
    return None if _missing(value) else bool(value)


def _str(value) -> str | None:
    return None if _missing(value) else str(value)


def _float_list(series: pd.Series) -> list[float | None]:
    if pd.api.types.is_timedelta64_dtype(series):
        series = series.dt.total_seconds()
    values = series.to_numpy(dtype=float, na_value=np.nan)
    out = values.tolist()
    if np.isnan(values).any():
        out = [None if v != v else v for v in out]
    return out


def _cast_list(series: pd.Series, cast) -> list:
    if series.isna().any():
        return [None if pd.isna(v) else cast(v) for v in series.tolist()]
    return [cast(v) for v in series.tolist()]


def _stored_event(session: Session) -> StoredEvent:
    event = session.event
    return StoredEvent(
        round=int(event["RoundNumber"]),
        name=str(event["EventName"]),
        official_name=_str(event.get("OfficialEventName")),
        country=str(event["Country"]),
        location=str(event["Location"]),
        date=str(event["EventDate"].date()),
        format=str(event["EventFormat"]),
    )


def _stored_drivers(session: Session) -> list[StoredDriver]:
    best = {}
    laps = session.laps
    if laps is not None and not laps.empty:
        best = laps.dropna(subset=["LapTime"]).groupby("DriverNumber")["LapTime"].min().to_dict()

    drivers = []
    for row in session.results.to_dict("records"):
        number = str(row["DriverNumber"])
        drivers.append(StoredDriver(
            number=number,
            abbreviation=_str(row.get("Abbreviation")) or None,
            full_name=_str(row.get("FullName")),
            broadcast_name=_str(row.get("BroadcastName")),
            team_name=_str(row.get("TeamName")),
            team_color=_str(row.get("TeamColor")),
            status=_str(row.get("Status")),
            classified_position=_str(row.get("ClassifiedPosition")),
            position=_int(row.get("Position")),
            grid_position=_int(row.get("GridPosition")),
            time=_seconds(row.get("Time")),
            laps=_int(row.get("Laps")),
            points=_float(row.get("Points")),
            q1=_seconds(row.get("Q1")),
            q2=_seconds(row.get("Q2")),
            q3=_seconds(row.get("Q3")),
            best_lap_time=_seconds(best.get(number)),
        ))
    return drivers


def _stored_weather(session: Session) -> StoredWeather | None:
    try:
        weather = session.weather_data
    except DataNotLoadedError:
        return None
    if weather is None or weather.empty:
        return None
    return StoredWeather(
        time=_float_list(weather["Time"]),
        air_temp=_float_list(weather["AirTemp"]),
        track_temp=_float_list(weather["TrackTemp"]),
        humidity=_float_list(weather["Humidity"]),
        pressure=_float_list(weather["Pressure"]),
        wind_speed=_float_list(weather["WindSpeed"]),
        wind_direction=_float_list(weather["WindDirection"]),
        rainfall=_cast_list(weather["Rainfall"], bool),
    )


def _fastest_lap(session: Session) -> StoredFastestLap | None:
    try:
        lap = session.laps.pick_fastest()
    except Exception:
        logger.exception("Could not pick the fastest lap")
        return None
    if lap is None or _missing(lap.get("LapTime")) or _missing(lap.get("LapNumber")):
        return None
    return StoredFastestLap(driver=str(lap["Driver"]), lap_number=int(lap["LapNumber"]), lap_time=_seconds(lap["LapTime"]))


def _qualifying_parts(session: Session) -> dict:
    """Maps a lap's index in session.laps to its qualifying part (1-3)."""
    if session.name not in QUALIFYING_SESSION_NAMES:
        return {}
    try:
        parts = session.laps.split_qualifying_sessions()
    except Exception:
        logger.warning("Could not split %s into qualifying parts", session, exc_info=True)
        return {}
    return {
        index: number
        for number, part in enumerate(parts, start=1)
        if part is not None
        for index in part.index
    }


def _telemetry_loaded(session: Session) -> bool:
    try:
        return bool(session.car_data)
    except DataNotLoadedError:
        return False


def _missing_parts(session: Session) -> list[str]:
    """Parts of a loaded session that came back empty.

    FastF1 reports some failed requests only as a warning, e.g. "Car position
    data is unavailable!", so these are checked on the data itself.
    """

    def loaded(attr: str):
        try:
            return getattr(session, attr)
        except DataNotLoadedError:
            return None

    missing = []
    laps = loaded("laps")
    drivers = [] if laps is None else [str(n) for n in laps["DriverNumber"].dropna().unique()]
    if not drivers:
        missing.append("laps")
    for attr, label in (("car_data", "car data"), ("pos_data", "position data")):
        data = loaded(attr) or {}
        absent = [d for d in drivers if d not in data or data[d].empty]
        if absent:
            missing.append(f"{label} for {len(absent)} of {len(drivers)} drivers")
    for attr, label in (
        ("results", "results"),
        ("weather_data", "weather"),
        ("race_control_messages", "race control messages"),
    ):
        data = loaded(attr)
        if data is None or data.empty:
            missing.append(label)
    return missing


def _lap_telemetry(lap: Lap, driver: str, lap_number: int) -> StoredLapTelemetry | None:
    try:
        car = lap.get_car_data().add_distance()
    except Exception:
        logger.debug("No telemetry for %s lap %s", driver, lap_number, exc_info=True)
        return None
    if car.empty:
        return None
    # Some sessions (e.g. early 2018) lack position data for some or all laps;
    # the car data is still worth keeping without the track position.
    try:
        pos = lap.get_pos_data()
    except Exception:
        logger.debug("No position data for %s lap %s", driver, lap_number, exc_info=True)
        pos = pd.DataFrame(columns=["Time", "X", "Y"])
    if pos.empty:
        pos = pd.DataFrame(columns=["Time", "X", "Y"])
    return StoredLapTelemetry(
        driver=driver,
        lap_number=lap_number,
        car=StoredCarData(
            time=_float_list(car["Time"]),
            speed=_float_list(car["Speed"]),
            throttle=_float_list(car["Throttle"]),
            brake=_cast_list(car["Brake"], bool),
            gear=_cast_list(car["nGear"], int),
            drs=_cast_list(car["DRS"], int),
            rpm=_float_list(car["RPM"]),
            distance=_float_list(car["Distance"]),
        ),
        pos=StoredPosData(
            time=_float_list(pos["Time"]),
            x=_float_list(pos["X"]),
            y=_float_list(pos["Y"]),
        ),
    )


def _stored_lap(lap: Lap, qualifying_part: int | None, has_telemetry: bool) -> StoredLap:
    return StoredLap(
        lap_number=_int(lap.get("LapNumber")),
        time=_seconds(lap.get("Time")),
        lap_start_time=_seconds(lap.get("LapStartTime")),
        lap_time=_seconds(lap.get("LapTime")),
        sector1=_seconds(lap.get("Sector1Time")),
        sector2=_seconds(lap.get("Sector2Time")),
        sector3=_seconds(lap.get("Sector3Time")),
        compound=_str(lap.get("Compound")),
        tyre_life=_int(lap.get("TyreLife")),
        fresh_tyre=_bool(lap.get("FreshTyre")),
        stint=_int(lap.get("Stint")),
        position=_int(lap.get("Position")),
        pit_in_time=_seconds(lap.get("PitInTime")),
        pit_out_time=_seconds(lap.get("PitOutTime")),
        track_status=_str(lap.get("TrackStatus")),
        is_personal_best=_bool(lap.get("IsPersonalBest")) or False,
        is_accurate=_bool(lap.get("IsAccurate")),
        deleted=_bool(lap.get("Deleted")),
        deleted_reason=_str(lap.get("DeletedReason")) or None,
        qualifying_part=qualifying_part,
        has_telemetry=has_telemetry,
    )


def _driver_order(session: Session, drivers: list[StoredDriver]) -> list[str]:
    """Drivers with laps: classification order first, then anyone else."""
    with_laps = list(dict.fromkeys(str(d) for d in session.laps["Driver"].dropna()))
    ordered = [d.abbreviation for d in drivers if d.abbreviation in with_laps]
    return ordered + [d for d in with_laps if d not in ordered]


def export_loaded_session(
    archive: SessionArchive,
    session: Session,
    year: int,
    event_id: str,
    identifier: str,
    *,
    now: datetime,
    load_failures: list[str] | None = None,
    upload_workers: int = 16,
) -> StoredSession:
    """Write a session loaded with laps, telemetry and weather to the archive.

    Laps, telemetry and the circuit are written first and session.json last,
    so readers only see a session once all of its objects exist.
    """
    started = time.monotonic()
    identifier = identifier.upper()
    start = session_start_utc(session)
    drivers = _stored_drivers(session)
    lap_drivers = _driver_order(session, drivers) if session.laps is not None and not session.laps.empty else []
    parts = _qualifying_parts(session)
    telemetry_loaded = _telemetry_loaded(session)
    telemetry_count = 0

    with ThreadPoolExecutor(max_workers=upload_workers) as pool:
        uploads: list[Future] = []
        for driver in lap_drivers:
            driver_laps = session.laps.pick_drivers(driver)
            stored_laps = []
            for index, lap in driver_laps.iterlaps():
                lap_number = _int(lap.get("LapNumber"))
                telemetry = None
                if telemetry_loaded and lap_number is not None:
                    telemetry = _lap_telemetry(lap, driver, lap_number)
                if telemetry is not None:
                    uploads.append(pool.submit(archive.put_lap_telemetry, year, event_id, identifier, telemetry))
                    telemetry_count += 1
                stored_laps.append(_stored_lap(lap, parts.get(index), telemetry is not None))
            numbers = driver_laps["DriverNumber"].dropna()
            laps = StoredDriverLaps(
                driver=driver,
                driver_number=str(numbers.iloc[0]) if not numbers.empty else None,
                laps=stored_laps,
            )
            uploads.append(pool.submit(archive.put_driver_laps, year, event_id, identifier, laps))

        if session.name == session.event.get("Session1") and telemetry_loaded:
            try:
                circuit = StoredCircuit.model_validate(build_circuit_info(session))
            except Exception:
                logger.exception("Could not build circuit info for %s %s", year, event_id)
            else:
                uploads.append(pool.submit(archive.put_circuit, year, event_id, circuit))

        for upload in uploads:
            upload.result()

    stored = StoredSession(
        exported_at=now,
        fastf1_version=fastf1.__version__,
        results_final=results_final(session_end_utc(session, start), now),
        year=year,
        event_id=event_id.lower(),
        identifier=identifier,
        name=session.name,
        start_utc=start,
        event=_stored_event(session),
        drivers=drivers,
        lap_drivers=lap_drivers,
        fastest_lap=_fastest_lap(session) if lap_drivers else None,
        weather=_stored_weather(session),
        load_failures=load_failures or [],
    )
    archive.put_session(stored)
    logger.info(
        "Exported %s %s %s: %d drivers, %d laps with telemetry in %.1fs",
        year, event_id, identifier, len(lap_drivers), telemetry_count, time.monotonic() - started,
    )
    return stored


class IncompleteLoadError(RuntimeError):
    """FastF1 failed to load part of a session, so exporting it would archive
    the session with that part missing for good."""

    def __init__(self, failures: list[str]):
        super().__init__("FastF1 failed to load " + "; ".join(failures))
        self.failures = failures


class _LoadFailures(logging.Handler):
    """Collects the errors FastF1 catches while loading a session.

    FastF1 wraps each part of Session.load in a catch-all that logs a warning
    and leaves that part empty, so a network error would otherwise go
    unnoticed. It logs each caught exception at DEBUG with exc_info.
    """

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self._thread = threading.get_ident()
        self.failures: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        # Loads in other threads (e.g. API requests) aren't this export's.
        if record.thread == self._thread and record.exc_info and record.exc_info[1] is not None:
            self.failures.append(f"{record.getMessage()} ({record.exc_info[1]!r})")


@contextmanager
def _capture_load_failures() -> Iterator[_LoadFailures]:
    fastf1_logger = logging.getLogger("fastf1")
    handler = _LoadFailures()
    fastf1_logger.addHandler(handler)
    try:
        yield handler
    finally:
        fastf1_logger.removeHandler(handler)


def export_session(
    archive: SessionArchive,
    year: int,
    event_id: str,
    identifier: str,
    *,
    force: bool = False,
    overwrite: bool = False,
    allow_incomplete: bool = False,
    now: datetime | None = None,
) -> ExportOutcome:
    """Load a session from FastF1 and export it, unless it isn't ready yet or
    is already exported (see skip_reason).

    Raises IncompleteLoadError when FastF1 fails to load part of the session,
    unless allow_incomplete is set for data that doesn't exist upstream.
    """
    now = now or datetime.now(timezone.utc)
    session = resolve_session(year, event_id, identifier)
    end = session_end_utc(session, session_start_utc(session))
    existing = archive.get_session(year, event_id, identifier)
    reason = skip_reason(existing, end, now, force=force, overwrite=overwrite)
    if reason is not None:
        logger.info("Skipping %s %s %s: %s", year, event_id, identifier, reason.value)
        return reason
    with _capture_load_failures() as load:
        # Race control messages are what FastF1 marks deleted laps (and so
        # personal bests and quali-like results) from.
        session.load(laps=True, telemetry=True, weather=True, messages=True)
    failures = load.failures + _missing_parts(session)
    if failures and not allow_incomplete:
        raise IncompleteLoadError(failures)
    export_loaded_session(archive, session, year, event_id, identifier, now=now, load_failures=failures)
    return ExportOutcome.EXPORTED
