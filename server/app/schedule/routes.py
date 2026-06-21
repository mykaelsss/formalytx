from fastapi import APIRouter, Response
from app.schedule.services import get_schedule, get_event, get_event_detailed, get_circuit_info, get_podium, get_results
from app.caching import cache_control_for, cache_control_for_year
from .services import SessionDetailConfig

router = APIRouter()

@router.get("/{year}")
def schedule(year: int, response: Response):
    data = get_schedule(year)
    response.headers["Cache-Control"] = cache_control_for_year(year)
    return data

@router.get("/{year}/{event_id}")
def event_detail(year: int, event_id: str, response: Response):
    data = get_event(year, event_id)
    response.headers["Cache-Control"] = cache_control_for(year, event_id, "R")
    return data

@router.get("/{year}/{event_id}/detailed")
def event_detail_detailed(year: int, event_id: str, response: Response, weather: bool = True, laps: bool = True):
    config = SessionDetailConfig(weather, laps)
    data = get_event_detailed(year, event_id, config)
    response.headers["Cache-Control"] = cache_control_for(year, event_id, "R")
    return data

@router.get("/{year}/{event_id}/{identifier}/results")
def results(year: int, event_id: str, identifier: str, response: Response):
    data = get_results(year, event_id, identifier)
    response.headers["Cache-Control"] = cache_control_for(year, event_id, identifier)
    return data


@router.get("/{year}/{event_id}/podium")
def podium(year: int, event_id: str, response: Response):
    data = get_podium(year, event_id)
    response.headers["Cache-Control"] = cache_control_for(year, event_id, "R")
    return data


@router.get("/{year}/{event_id}/circuit")
def circuit(year: int, event_id: str, response: Response):
    data = get_circuit_info(year, event_id)
    response.headers["Cache-Control"] = cache_control_for(year, event_id, 1)
    return data
