import fastf1

IDENTIFIER_MAP = {
    "FP1": "Practice 1",
    "FP2": "Practice 2",
    "FP3": "Practice 3",
    "Q": "Qualifying",
    "S": "Sprint",
    "SQ": "Sprint Qualifying",
    "R": "Race",
}


def _get_session_date(event, identifier: str):
    session_name = IDENTIFIER_MAP.get(identifier.upper(), identifier)
    for i in range(1, 6):
        if event.get(f"Session{i}") == session_name:
            return str(event.get(f"Session{i}DateUtc"))
    return None


async def load_session(year: int, round: int, identifier: str):
    session = fastf1.get_session(year, round, identifier)
    session.load()

    session_date = _get_session_date(session.event, identifier)

    return {
        "event": session.event["EventName"],
        "country": session.event["Country"],
        "location": session.event["Location"],
        "round": int(session.event["RoundNumber"]),
        "session": session.name,
        "date": session_date,
    }
