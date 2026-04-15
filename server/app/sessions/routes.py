from fastapi import APIRouter
from app.sessions.services import load_session

router = APIRouter()

@router.get("/{year}/{round}/{identifier}")
async def get_session_data(year: int, round: int, identifier: str):
    return await load_session(year, round, identifier)