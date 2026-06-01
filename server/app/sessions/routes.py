from fastapi import APIRouter
from app.sessions.services import get_session, get_driver_laps, get_lap_telemetry

router = APIRouter()

@router.get("/{year}/{round}/{identifier}")
def session_info(year:int, round: int, identifier: str):
    return get_session(year, round, identifier)

@router.get("/{year}/{round}/{identifier}/laps")
def driver_laps(year: int, round: int, identifier: str, drivers: str = ''):
    return get_driver_laps(year, round, identifier, drivers)

@router.get("/{year}/{round}/{identifier}/laps/telemetry")
def lap_telemetry(year: int, round: int, identifier: str, selected_laps: str):
    return get_lap_telemetry(year, round, identifier, selected_laps)