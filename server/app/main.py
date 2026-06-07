from functools import lru_cache

import os
from contextlib import asynccontextmanager

import fastf1
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from app.sessions.routes import router as session_router
from app.schedule.routes import router as schedule_router

@lru_cache
def get_settings(): 
    return config.Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
      settings = get_settings()
      os.makedirs(settings.fastf1_cache_dir, exist_ok=True)
      fastf1.Cache.enable_cache(settings.fastf1_cache_dir)
      yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(schedule_router, prefix='/schedule')
app.include_router(session_router, prefix='/sessions')

@app.get("/health")
def health():
    return {"status": "ok"}