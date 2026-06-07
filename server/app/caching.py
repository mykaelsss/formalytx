from datetime import datetime, timezone, timedelta

import fastf1
import pandas as pd

from app.schedule.services import SESSION_DURATION_MINUTES
from app.sessions.services import IDENTIFIER_MAP

# Once a session ends, lap/telemetry data is fixed, but classification can still
# shift for a while as stewards apply penalties/DSQs. Hold off on immutable
# caching until results have settled.
SETTLE_BUFFER = timedelta(days=2)

LIVE = "public, max-age=60"
SETTLING = "public, max-age=300"
IMMUTABLE = "public, max-age=31536000, immutable"


def _session_end(year: int, round: int, identifier: str) -> datetime | None:
    event = fastf1.get_event(year, round)
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


def cache_control_for(year: int, round: int, identifier: str) -> str:
    """Cache-Control for a single session's data, gated on when it finalizes."""
    try:
        end = _session_end(year, round, identifier)
    except Exception:
        return SETTLING
    if end is None:
        return SETTLING
    now = datetime.now(timezone.utc)
    if now < end:
        return LIVE
    if now < end + SETTLE_BUFFER:
        return SETTLING
    return IMMUTABLE


def cache_control_for_year(year: int) -> str:
    """Cache-Control for the season schedule list. Past seasons are fixed; the
    current/future season's per-event status flips over time, so keep it short."""
    return IMMUTABLE if year < datetime.now(timezone.utc).year else SETTLING
