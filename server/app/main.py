from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.sessions.routes import router as session_router
from app.schedule.routes import router as schedule_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(schedule_router, prefix='/schedule')
app.include_router(session_router, prefix='/sessions')