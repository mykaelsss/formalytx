import logging
from datetime import datetime, timezone, timedelta

import pandas as pd

from app.archive import reader
from app.archive.models import StoredSession
from app.schedule.services import SESSION_DURATION_MINUTES, TESTING_SESSION_MINUTES
from app.sessions.services import IDENTIFIER_MAP
from app.utils import resolve_event

logger = logging.getLogger("uvicorn.error")

# Once a session ends, lap/telemetry data is fixed, but classification can still
# shift for a while as stewards apply penalties/DSQs. Hold off on immutable
# caching until results have settled.
SETTLE_BUFFER = timedelta(days=2)

LIVE = "public, no-cache"
SETTLING = "public, max-age=0, s-maxage=3600"
PAST_SEASON = "public, max-age=0, s-maxage=604800"


def _stored_session_end(stored: StoredSession) -> datetime | None:
    start = stored.start_utc
    if start is None:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if stored.event.format == "testing":
        minutes = TESTING_SESSION_MINUTES
    else:
        minutes = SESSION_DURATION_MINUTES.get(stored.identifier, 60)
    return start + timedelta(minutes=minutes)


def _session_end(year: int, event_id: str, identifier: str | int) -> datetime | None:
    # An archived session's start comes from its summary, which the request has
    # already read and the reader caches. FastF1's schedule would do too, but
    # FastF1 revalidates it with GitHub every 5 minutes, and a stalled request
    # holds the response until it times out.
    archive = reader.current()
    stored = archive.session(year, event_id, identifier) if archive is not None else None
    if stored is not None:
        return _stored_session_end(stored)
    event = resolve_event(year, event_id)
    name = IDENTIFIER_MAP.get(identifier.upper(), identifier)
    for i in range(1, 6):
        if event.get(f"Session{i}") != name:
            continue
        start = event.get(f"Session{i}DateUtc")
        if start is None or pd.isna(start):
            return None
        start = pd.Timestamp(start).to_pydatetime()
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        return start + timedelta(minutes=SESSION_DURATION_MINUTES.get(identifier.upper(), 60))
    return None


def cache_control_for(year: int, event_id: str, identifier: str) -> str:
    """Cache-Control for a single session's data, gated on when it finalizes."""
    try:
        end = _session_end(year, event_id, identifier)
    except Exception:
        logger.exception(
            "Could not resolve session end for %s/%s/%s; falling back to SETTLING",
            year,
            event_id,
            identifier,
        )
        return SETTLING
    if end is None:
        return SETTLING
    now = datetime.now(timezone.utc)
    if now < end:
        return LIVE
    if now < end + SETTLE_BUFFER:
        return SETTLING
    return PAST_SEASON


def cache_control_for_year(year: int) -> str:
    """Cache-Control for the season schedule list. Past seasons are fixed; the
    current/future season's per-event status flips over time, so keep it short."""
    return PAST_SEASON if year < datetime.now(timezone.utc).year else SETTLING
