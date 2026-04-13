from fastapi import FastAPI
from app.sessions.routes import router as session_router
from app.schedule.routes import router as schedule_router

app = FastAPI()

app.include_router(schedule_router, prefix='/schedule')
app.include_router(session_router, prefix='/sessions')