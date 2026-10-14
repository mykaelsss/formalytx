import logging
from datetime import datetime, timezone, timedelta

from app.archive import reader
from app.schedule.services import SESSION_DURATION_MINUTES, TESTING_SESSION_MINUTES, find_event, season
from app.sessions.services import IDENTIFIER_MAP

logger = logging.getLogger("uvicorn.error")

# Once a session ends, lap/telemetry data is fixed, but classification can still
# shift for a while as stewards apply penalties/DSQs. Hold off on immutable
# caching until results have settled.
SETTLE_BUFFER = timedelta(days=2)

LIVE = "public, no-cache"
SETTLING = "public, max-age=0, s-maxage=3600"
PAST_SEASON = "public, max-age=0, s-maxage=604800"


def _end(start: datetime | None, event_format: str, identifier: str) -> datetime | None:
    if start is None:
        return None
    start = start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start.astimezone(timezone.utc)
    if event_format == "testing":
        minutes = TESTING_SESSION_MINUTES
    else:
        minutes = SESSION_DURATION_MINUTES.get(identifier.upper(), 60)
    return start + timedelta(minutes=minutes)


def _session_end(year: int, event_id: str, identifier: str | int) -> datetime | None:
    # Neither read goes to FastF1, whose schedule it revalidates with GitHub
    # every 5 minutes, holding the response when that stalls. An archived
    # session's summary, which the request has already read and the reader
    # caches, has its start; the season's schedule has the others'.
    archive = reader.current()
    stored = archive.session(year, event_id, identifier) if archive is not None else None
    if stored is not None:
        return _end(stored.start_utc, stored.event.format, stored.identifier)
    event = find_event(season(year), event_id)
    name = IDENTIFIER_MAP.get(identifier.upper(), identifier)
    for session in event.sessions:
        if session.name == name:
            return _end(session.start, event.format, identifier)
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
