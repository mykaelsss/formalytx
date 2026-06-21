from fastapi import APIRouter, Response
from app.sessions.services import get_session, get_driver_laps, get_lap_telemetry
from app.caching import cache_control_for

router = APIRouter()

@router.get("/{year}/{event_id}/{identifier}")
def session_info(year:int, event_id: str, identifier: str, response: Response):
    data = get_session(year, event_id, identifier)
    response.headers["Cache-Control"] = cache_control_for(year, event_id, identifier)
    return data

@router.get("/{year}/{event_id}/{identifier}/laps")
def driver_laps(year: int, event_id: str, identifier: str, response: Response, drivers: str = ''):
    data = get_driver_laps(year, event_id, identifier, drivers)
    response.headers["Cache-Control"] = cache_control_for(year, event_id, identifier)
    return data

@router.get("/{year}/{event_id}/{identifier}/laps/telemetry")
def lap_telemetry(year: int, event_id: str, identifier: str, selected_laps: str, response: Response):
    data = get_lap_telemetry(year, event_id, identifier, selected_laps)
    response.headers["Cache-Control"] = cache_control_for(year, event_id, identifier)
    return data