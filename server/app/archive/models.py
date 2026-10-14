"""The stored format for exported sessions.

Each object holds processed FastF1 data in our own neutral shape, not an API
response. The server maps these to responses, so response changes don't need a
re-export; only data we never stored does. Times are in seconds, missing
values are None. Bump FORMAT_VERSION (which also changes the key prefix) for
any change that older objects can't be read as.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

FORMAT_VERSION = 1


class StoredEvent(BaseModel):
    round: int
    name: str
    official_name: str | None
    country: str
    location: str
    date: str
    format: str


class StoredScheduleSession(BaseModel):
    name: str
    # In the circuit's local time, with its UTC offset.
    start: datetime


class StoredScheduleEvent(BaseModel):
    round: int
    # r{round}, or t{n} for the season's n-th testing event, which has no round.
    event_id: str
    name: str
    official_name: str | None
    country: str
    location: str
    date: str
    format: str
    sessions: list[StoredScheduleSession]


class StoredSchedule(BaseModel):
    """A season's events as FastF1's schedule had them when exported.

    Events can still move or be replaced during the season, so the current
    season is exported again on every run. Statuses aren't stored: they're
    worked out from the dates when serving.
    """

    format_version: Literal[1] = FORMAT_VERSION
    exported_at: datetime
    fastf1_version: str
    year: int
    events: list[StoredScheduleEvent]


class StoredDriver(BaseModel):
    number: str
    abbreviation: str | None
    full_name: str | None
    broadcast_name: str | None
    team_name: str | None
    team_color: str | None
    status: str | None
    classified_position: str | None
    position: int | None
    grid_position: int | None
    time: float | None
    laps: int | None
    points: float | None
    q1: float | None
    q2: float | None
    q3: float | None
    # Fastest LapTime over all of the driver's laps, used for practice and
    # qualifying classifications built from lap times.
    best_lap_time: float | None


class StoredFastestLap(BaseModel):
    driver: str
    lap_number: int
    lap_time: float


class StoredWeather(BaseModel):
    time: list[float | None]
    air_temp: list[float | None]
    track_temp: list[float | None]
    humidity: list[float | None]
    pressure: list[float | None]
    wind_speed: list[float | None]
    wind_direction: list[float | None]
    rainfall: list[bool | None]


class StoredSession(BaseModel):
    """Written last, so its presence means the whole session was exported."""

    format_version: Literal[1] = FORMAT_VERSION
    exported_at: datetime
    fastf1_version: str
    # False while stewards can still change the classification; the session
    # is exported again once it's final.
    results_final: bool
    year: int
    event_id: str
    identifier: str
    name: str
    start_utc: datetime | None
    event: StoredEvent
    drivers: list[StoredDriver]
    # Driver keys with a laps object, in classification order.
    lap_drivers: list[str]
    fastest_lap: StoredFastestLap | None
    weather: StoredWeather | None
    # Parts FastF1 failed to load, when the session was exported anyway
    # (`--allow-incomplete`) because the data doesn't exist upstream.
    load_failures: list[str] = []


class StoredLap(BaseModel):
    lap_number: int | None
    time: float | None
    lap_start_time: float | None
    lap_time: float | None
    sector1: float | None
    sector2: float | None
    sector3: float | None
    compound: str | None
    tyre_life: int | None
    fresh_tyre: bool | None
    stint: int | None
    position: int | None
    pit_in_time: float | None
    pit_out_time: float | None
    track_status: str | None
    is_personal_best: bool
    is_accurate: bool | None
    deleted: bool | None
    deleted_reason: str | None
    # 1-3 for Q1-Q3 (or SQ1-SQ3); None outside qualifying.
    qualifying_part: int | None
    has_telemetry: bool


class StoredDriverLaps(BaseModel):
    format_version: Literal[1] = FORMAT_VERSION
    driver: str
    driver_number: str | None
    laps: list[StoredLap]


class StoredCarData(BaseModel):
    time: list[float | None]
    speed: list[float | None]
    throttle: list[float | None]
    brake: list[bool | None]
    gear: list[int | None]
    drs: list[int | None]
    rpm: list[float | None]
    distance: list[float | None]


class StoredPosData(BaseModel):
    time: list[float | None]
    x: list[float | None]
    y: list[float | None]


class StoredLapTelemetry(BaseModel):
    format_version: Literal[1] = FORMAT_VERSION
    driver: str
    lap_number: int
    car: StoredCarData
    pos: StoredPosData


class StoredCorner(BaseModel):
    x: float
    y: float
    number: int
    angle: float
    distance: float


class StoredCircuit(BaseModel):
    format_version: Literal[1] = FORMAT_VERSION
    rotation: float
    corners: list[StoredCorner]
    marshal_sectors: list[StoredCorner]
    sector_distances: list[float]
