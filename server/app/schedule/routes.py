from fastapi import APIRouter
from app.schedule.services import get_schedule, get_round

router = APIRouter()


@router.get("/{year}")
async def schedule(year: int):
    return get_schedule(year)


@router.get("/{year}/{round}")
async def round_detail(year: int, round: int):
    return get_round(year, round)
