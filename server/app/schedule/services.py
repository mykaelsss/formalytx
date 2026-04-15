import fastf1
from datetime import datetime, timezone


def get_schedule(year: int):
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    rounds = []

    for _, event in schedule.iterrows():
        rounds.append({
            "round": int(event["RoundNumber"]),
            "name": event["EventName"],
            "country": event["Country"],
            "location": event["Location"],
            "date": str(event["EventDate"].date()),
            "format": event["EventFormat"],
            "status": _event_status(event["EventDate"]),
        })

    return {"year": year, "rounds": rounds}


def get_round(year: int, round: int):
    event = fastf1.get_event(year, round)
    sessions = _get_sessions(event)

    return {
        "round": round,
        "year": year,
        "name": event["EventName"],
        "country": event["Country"],
        "location": event["Location"],
        "date": str(event["EventDate"].date()),
        "format": event["EventFormat"],
        "sessions": sessions,
    }


SESSION_NAME_TO_IDENTIFIER = {
    "Practice 1": "FP1",
    "Practice 2": "FP2",
    "Practice 3": "FP3",
    "Qualifying": "Q",
    "Sprint": "S",
    "Sprint Qualifying": "SQ",
    "Race": "R",
}


def _get_sessions(event):
    sessions = []
    for i in range(1, 6):
        name = event.get(f"Session{i}")
        date = event.get(f"Session{i}Date")
        if not name or str(name).strip() == "":
            continue
        sessions.append({
            "name": name,
            "identifier": SESSION_NAME_TO_IDENTIFIER.get(name, name),
            "date": str(date.date()) if hasattr(date, "date") else str(date),
            "status": _event_status(date),
        })
    return sessions


def _check_data_availability(year: int, round: int, identifier: str):
    try:
        session = fastf1.get_session(year, round, identifier)
        session.load(telemetry=False, weather=False, messages=False)
        laps = session.laps
        has_laps = laps is not None and not laps.empty
        has_telemetry = False
        if has_laps:
            try:
                tel = laps.iloc[0].get_telemetry()
                has_telemetry = tel is not None and not tel.empty
            except Exception:
                pass
        return {"telemetry_available": has_telemetry, "replay_available": has_telemetry}
    except Exception:
        return {"telemetry_available": False, "replay_available": False}


def _event_status(date):
    if date is None:
        return "unknown"
    now = datetime.now(timezone.utc)
    event_date = date if isinstance(date, datetime) else datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc)
    if event_date.tzinfo is None:
        event_date = event_date.replace(tzinfo=timezone.utc)
    return "upcoming" if event_date > now else "completed"
