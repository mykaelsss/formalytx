from fastapi import APIRouter
from app.sessions.services import load_session

router = APIRouter()

@router.get("/{year}/{round}/{identifier}")
async def getSessionData(year: int, round: int, identifier: int | str | None = None):
    return await load_session(year, round, identifier)