import fastf1

async def load_session(year: int, round: int, identifier: int | str | None = None):
    session = fastf1.get_session(year, round, identifier)
    session.load()
    return {"event": session.event["EventName"]}