from fastapi import APIRouter, Response
from app.schedule.services import get_schedule, get_round, get_round_detailed, get_circuit_info, get_podium, get_results
from app.caching import cache_control_for, cache_control_for_year
from .services import SessionDetailConfig

router = APIRouter()

@router.get("/{year}")
def schedule(year: int, response: Response):
    data = get_schedule(year)
    response.headers["Cache-Control"] = cache_control_for_year(year)
    return data

@router.get("/{year}/{round}")
def round_detail(year: int, round: int, response: Response):
    data = get_round(year, round)
    response.headers["Cache-Control"] = cache_control_for(year, round, "R")
    return data

@router.get("/{year}/{round}/detailed")
def round_detail_detailed(year: int, round: int, response: Response, weather: bool = True, laps: bool = True):
    config = SessionDetailConfig(weather, laps)
    data = get_round_detailed(year, round, config)
    response.headers["Cache-Control"] = cache_control_for(year, round, "R")
    return data

@router.get("/{year}/{round}/{identifier}/results")
def results(year: int, round: int, identifier: str, response: Response):
    data = get_results(year, round, identifier)
    response.headers["Cache-Control"] = cache_control_for(year, round, identifier)
    return data


@router.get("/{year}/{round}/podium")
def podium(year: int, round: int, response: Response):
    data = get_podium(year, round)
    response.headers["Cache-Control"] = cache_control_for(year, round, "R")
    return data


@router.get("/{year}/{round}/circuit")
def circuit(year: int, round: int, response: Response):
    data = get_circuit_info(year, round)
    response.headers["Cache-Control"] = cache_control_for(year, round, "R")
    return data
