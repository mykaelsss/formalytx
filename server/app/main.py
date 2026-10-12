from functools import lru_cache

import faulthandler
import logging
import os
import signal
from contextlib import asynccontextmanager

import fastf1
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastf1.exceptions import (
    DataNotLoadedError,
    ErgastError,
    FastF1CriticalError,
    InvalidSessionError,
    NoLapDataError,
    RateLimitExceededError,
)

from . import config
from app.archive import reader
from app.archive.archive import open_archive
from app.archive.reader import ArchiveReader, ArchiveUnavailable
from app.etag import ETagMiddleware
from app.fastf1_loader import configure_session_cache, install_request_timeouts, set_cache_dir, start_pruner
from app.sessions.routes import router as session_router
from app.schedule.routes import router as schedule_router
from app.utils import LockWaitTimeout

logger = logging.getLogger("uvicorn.error")

try:
    # Private module; raised by session.load() when live timing has no data.
    from fastf1._api import SessionNotAvailableError
except Exception:  # tolerate an upstream rename without breaking startup
    class SessionNotAvailableError(Exception):
        pass

@lru_cache
def get_settings(): 
    return config.Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    os.makedirs(settings.fastf1_cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(settings.fastf1_cache_dir)
    install_request_timeouts(
        settings.upstream_connect_timeout_seconds,
        settings.upstream_read_timeout_seconds,
    )
    set_cache_dir(settings.fastf1_cache_dir)
    configure_session_cache(settings.session_cache_size, settings.session_cache_idle_seconds)
    archive = open_archive(settings)
    reader.configure(ArchiveReader(archive) if archive is not None else None)
    if archive is None:
        logger.warning("No session archive configured; every session is loaded through FastF1")
    else:
        logger.info("Serving archived sessions from %s", settings.r2_bucket or settings.archive_local_dir)
    # `kill -USR1 <pid>` dumps every thread's stack to stderr (the deploy logs)
    # so a stuck request can be diagnosed in production without a restart.
    if hasattr(signal, "SIGUSR1"):
        faulthandler.register(signal.SIGUSR1, all_threads=True)
    stop_pruner = start_pruner(
        settings.fastf1_cache_dir,
        settings.cache_high_water,
        settings.cache_low_water,
        settings.cache_prune_interval_seconds,
    )
    try:
        yield
    finally:
        stop_pruner.set()
        reader.configure(None)

app = FastAPI(lifespan=lifespan)


def _error(status: int, detail: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail}, headers=headers)


async def _not_found(request: Request, exc: Exception) -> JSONResponse:
    # Invalid year/round/session or a session the API has no usable data for.
    logger.info("404 for %s: %s", request.url.path, exc)
    return _error(404, str(exc) or "The requested session data is not available.")


async def _rate_limited(request: Request, exc: Exception) -> JSONResponse:
    logger.warning("Upstream rate limit for %s: %s", request.url.path, exc)
    return _error(
        503,
        "The upstream data provider is rate limiting requests. Please try again shortly.",
        headers={"Retry-After": "60"},
    )


async def _upstream_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Upstream data error for %s: %s", request.url.path, exc)
    return _error(502, "Failed to retrieve data from the upstream provider.")


async def _upstream_request_failed(request: Request, exc: Exception) -> JSONResponse:
    # FastF1 swallows most request errors itself; these are the ones that escape.
    if isinstance(exc, requests.Timeout):
        logger.error("Upstream timeout for %s: %s", request.url.path, exc)
        return _error(504, "The upstream data provider did not respond in time. Please try again shortly.")
    return await _upstream_error(request, exc)


async def _lock_wait_timeout(request: Request, exc: Exception) -> JSONResponse:
    # Another request for the same data is still running (or stuck upstream).
    logger.warning("Lock wait timed out for %s: %s", request.url.path, exc)
    return _error(
        503,
        "This data is still being loaded. Please try again shortly.",
        headers={"Retry-After": "30"},
    )


async def _archive_unavailable(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Archive unavailable for %s: %s", request.url.path, exc)
    return _error(
        503,
        "Session data is temporarily unavailable. Please try again shortly.",
        headers={"Retry-After": "30"},
    )


for _exc in (ValueError, InvalidSessionError, NoLapDataError, SessionNotAvailableError, DataNotLoadedError):
    app.add_exception_handler(_exc, _not_found)
app.add_exception_handler(RateLimitExceededError, _rate_limited)
app.add_exception_handler(FastF1CriticalError, _upstream_error)
app.add_exception_handler(ErgastError, _upstream_error)
app.add_exception_handler(requests.RequestException, _upstream_request_failed)
app.add_exception_handler(LockWaitTimeout, _lock_wait_timeout)
app.add_exception_handler(ArchiveUnavailable, _archive_unavailable)

app.add_middleware(ETagMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(schedule_router, prefix='/schedule')
app.include_router(session_router, prefix='/sessions')

class Health(BaseModel):
    status: str


@app.get("/health", response_model=Health)
def health():
    return {"status": "ok"}