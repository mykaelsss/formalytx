from fastapi import APIRouter
from app.schedule.services import get_schedule, get_round, get_round_detailed, get_circuit_info, get_podium, get_results
from .services import SessionDetailConfig

router = APIRouter()

@router.get("/{year}")
def schedule(year: int):
    return get_schedule(year)

@router.get("/{year}/{round}")
def round_detail(year: int, round: int):
    return get_round(year, round)

@router.get("/{year}/{round}/detailed")
def round_detail_detailed(year: int, round: int, weather: bool = True, laps: bool = True):
    config = SessionDetailConfig(weather, laps)
    return get_round_detailed(year, round, config)

@router.get("/{year}/{round}/{identifier}/results")
def results(year: int, round: int, identifier: str):
    return get_results(year, round, identifier)


@router.get("/{year}/{round}/podium")
def podium(year: int, round: int):
    return get_podium(year, round)


@router.get("/{year}/{round}/circuit")
def circuit(year: int, round: int):
    return get_circuit_info(year, round)
