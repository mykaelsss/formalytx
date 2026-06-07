from fastapi import APIRouter, Response
from app.sessions.services import get_session, get_driver_laps, get_lap_telemetry
from app.caching import cache_control_for

router = APIRouter()

@router.get("/{year}/{round}/{identifier}")
def session_info(year:int, round: int, identifier: str, response: Response):
    data = get_session(year, round, identifier)
    response.headers["Cache-Control"] = cache_control_for(year, round, identifier)
    return data

@router.get("/{year}/{round}/{identifier}/laps")
def driver_laps(year: int, round: int, identifier: str, response: Response, drivers: str = ''):
    data = get_driver_laps(year, round, identifier, drivers)
    response.headers["Cache-Control"] = cache_control_for(year, round, identifier)
    return data

@router.get("/{year}/{round}/{identifier}/laps/telemetry")
def lap_telemetry(year: int, round: int, identifier: str, selected_laps: str, response: Response):
    data = get_lap_telemetry(year, round, identifier, selected_laps)
    response.headers["Cache-Control"] = cache_control_for(year, round, identifier)
    return data