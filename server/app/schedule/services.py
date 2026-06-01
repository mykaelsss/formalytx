import fastf1
import pandas as pd
from datetime import datetime, timezone, timedelta
from fastf1.core import Session
from dataclasses import dataclass

@dataclass
class SessionDetailConfig:
    weather: bool = True
    laps: bool = True

SESSION_NAME_TO_IDENTIFIER = {
    "Practice 1": "FP1",
    "Practice 2": "FP2",
    "Practice 3": "FP3",
    "Qualifying": "Q",
    "Sprint": "S",
    "Sprint Qualifying": "SQ",
    "Race": "R",
}

SESSION_DURATION_MINUTES = {
    "FP1": 60, "FP2": 60, "FP3": 60,
    "Q": 60,
    "SQ": 60,
    "S": 30,
    "R": 120,
}

def get_schedule(year: int):
    schedule = fastf1.get_event_schedule(year)
    rounds = []

    for _, event in schedule.iterrows():
        status = _event_status(event["EventDate"])
        round_num = int(event["RoundNumber"])
        rounds.append({
            "round": round_num,
            "country": event["Country"],
            "location": event["Location"],
            "official_event_name": event['OfficialEventName'],
            "event_name": event["EventName"],
            "event_date_start": str(event["Session1DateUtc"].date()) if event.get("Session1DateUtc") is not None else str(event["EventDate"].date()),
            "event_date_end": str(event["EventDate"].date()),
            "event_format": event["EventFormat"],
            "status": status,
        })

    return {"year": year, "rounds": rounds}

def get_results(year: int, round: int, identifier: str):
    session = fastf1.get_session(year, round, identifier)
    uid = identifier.upper()
    if uid in {"FP1", "FP2", "FP3"}:
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        return _practice_results(session)
    elif uid in {"Q", "SQ"}:
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        return _qualifying_results(session)
    else:
        session.load(laps=False, telemetry=False, weather=False, messages=False)
        return _race_results(session)


def _race_results(session: Session):
    results = session.results.copy()
    results['Position'] = pd.to_numeric(results['Position'], errors='coerce')
    results = results.dropna(subset=['Position']).sort_values('Position')

    rows = []
    for _, row in results.iterrows():
        position = int(row['Position'])
        time_val = row.get('Time')
        if time_val is not None and not pd.isna(time_val):
            secs = pd.Timedelta(time_val).total_seconds()
            if position == 1:
                h = int(secs // 3600)
                m = int((secs % 3600) // 60)
                s = secs % 60
                time_str = f"{h}:{m:02d}:{s:06.3f}"
            else:
                time_str = f"+{secs:.3f}s"
        else:
            time_str = None

        rows.append({
            "position": position,
            "code": str(row.get('Abbreviation', '')),
            "full_name": str(row.get('FullName', '')),
            "team": str(row.get('TeamName', '')),
            "team_color": str(row.get('TeamColor', '')),
            "grid": int(row['GridPosition']) if not pd.isna(row.get('GridPosition')) else None,
            "laps": int(row['Laps']) if not pd.isna(row.get('Laps')) else None,
            "time": time_str,
            "q1": None, "q2": None, "q3": None,
            "status": str(row.get('Status', '')),
            "points": float(row['Points']) if not pd.isna(row.get('Points')) else 0.0,
        })
    return rows


def _qualifying_results(session: Session):
    results = session.results.copy()
    results['Position'] = pd.to_numeric(results['Position'], errors='coerce')
    ranked = results.dropna(subset=['Position']).sort_values('Position')

    # Fall back to lap times if results has no positions (e.g. SQ or incomplete cache)
    if ranked.empty:
        fastest = (
            session.laps
            .dropna(subset=['LapTime'])
            .groupby('DriverNumber', as_index=False)['LapTime']
            .min()
            .sort_values('LapTime')
            .reset_index(drop=True)
        )
        rows = []
        for pos, row in fastest.iterrows():
            driver_num = str(row['DriverNumber'])
            info = results.loc[driver_num] if driver_num in results.index else None
            rows.append({
                "position": pos + 1,
                "code": str(info['Abbreviation']) if info is not None else driver_num,
                "full_name": str(info['FullName']) if info is not None else '',
                "team": str(info['TeamName']) if info is not None else '',
                "team_color": str(info['TeamColor']) if info is not None else '',
                "grid": None, "laps": None, "time": None,
                "q1": _format_lap_time(row['LapTime']),
                "q2": None, "q3": None,
                "status": None, "points": 0.0,
            })
        return rows

    rows = []
    for _, row in ranked.iterrows():
        rows.append({
            "position": int(row['Position']),
            "code": str(row.get('Abbreviation', '')),
            "full_name": str(row.get('FullName', '')),
            "team": str(row.get('TeamName', '')),
            "team_color": str(row.get('TeamColor', '')),
            "grid": None, "laps": None, "time": None,
            "q1": _format_lap_time(row.get('Q1')),
            "q2": _format_lap_time(row.get('Q2')),
            "q3": _format_lap_time(row.get('Q3')),
            "status": None, "points": 0.0,
        })
    return rows


def _practice_results(session: Session):
    results = session.results
    fastest = (
        session.laps
        .dropna(subset=['LapTime'])
        .groupby('DriverNumber', as_index=False)['LapTime']
        .min()
        .sort_values('LapTime')
        .reset_index(drop=True)
    )
    leader_time = fastest.iloc[0]['LapTime'] if not fastest.empty else None

    rows = []
    for pos, row in fastest.iterrows():
        driver_num = str(row['DriverNumber'])
        info = results.loc[driver_num] if driver_num in results.index else None
        position = pos + 1
        secs = pd.Timedelta(row['LapTime']).total_seconds()
        if position == 1:
            m = int(secs // 60)
            s = secs % 60
            time_str = f"{m}:{s:06.3f}"
        else:
            gap = (pd.Timedelta(row['LapTime']) - pd.Timedelta(leader_time)).total_seconds()
            time_str = f"+{gap:.3f}s"

        rows.append({
            "position": position,
            "code": str(info['Abbreviation']) if info is not None else driver_num,
            "full_name": str(info['FullName']) if info is not None else '',
            "team": str(info['TeamName']) if info is not None else '',
            "team_color": str(info['TeamColor']) if info is not None else '',
            "grid": None,
            "laps": None,
            "time": time_str,
            "q1": None, "q2": None, "q3": None,
            "status": None,
            "points": 0.0,
        })
    return rows

def _format_lap_time(td) -> str | None:
    if td is None or pd.isna(td):
        return None
    secs = pd.Timedelta(td).total_seconds()
    m = int(secs // 60)
    s = secs % 60
    return f"{m}:{s:06.3f}"

def get_podium(year: int, round: int):
    try:
        session = fastf1.get_session(year, round, 'R')
        session.load(telemetry=False, weather=False, messages=False)
        results = session.results

        # Normalise Position to numeric — older years may have strings or floats
        results = results.copy()
        results['Position'] = pd.to_numeric(results['Position'], errors='coerce')
        results = results.dropna(subset=['Position'])
        results = results.sort_values('Position').head(3)

        podium = []
        for _, row in results.iterrows():
            position = int(row['Position'])

            # Driver code: prefer Abbreviation, fall back to BroadcastName initials or DriverNumber
            code = str(row.get('Abbreviation', '') or '').strip()
            if not code or code == 'nan':
                broadcast = str(row.get('BroadcastName', '') or '').strip()
                code = broadcast.split()[-1][:3].upper() if broadcast and broadcast != 'nan' else str(int(row.get('DriverNumber', position)))

            # Time: winner gets total race time, others get gap
            time_val = row.get('Time')
            if time_val is not None and not (isinstance(time_val, float) and pd.isna(time_val)):
                try:
                    secs = pd.Timedelta(time_val).total_seconds()
                    if position == 1:
                        h = int(secs // 3600)
                        m = int((secs % 3600) // 60)
                        s = secs % 60
                        time_str = f"{h}:{m:02d}:{s:06.3f}"
                    else:
                        time_str = f"+{secs:.3f}s"
                except Exception:
                    time_str = str(row.get('Status', ''))
            else:
                time_str = str(row.get('Status', ''))

            podium.append({"position": position, "code": code, "time": time_str})

        return podium
    except Exception:
        return []


def get_circuit_info(year: int, round: int, identifier: str = 'R'):
    try:
        session = fastf1.get_session(year, round, identifier)
        session.load(laps=True, telemetry=True, weather=False, messages=False)
        circuit_info = session.get_circuit_info()

        sector_distances = []
        try:
            fastest_lap = session.laps.pick_fastest()
            if fastest_lap is not None:
                s1 = fastest_lap.get("Sector1Time")
                s2 = fastest_lap.get("Sector2Time")
                if s1 is not None and s2 is not None and not pd.isna(s1) and not pd.isna(s2):
                    tel = fastest_lap.get_telemetry()
                    if tel is not None and not tel.empty:
                        tel_time = tel["Time"].dt.total_seconds()
                        s1_secs = pd.Timedelta(s1).total_seconds()
                        s2_secs = s1_secs + pd.Timedelta(s2).total_seconds()
                        for t in [s1_secs, s2_secs]:
                            mask = tel_time >= t
                            if mask.any():
                                sector_distances.append(float(tel.loc[mask.idxmax(), "Distance"]))
        except Exception as e:
            print(f"Error computing sector distances: {e}")

        return {
            "rotation": circuit_info.rotation,
            "corners": circuit_info.corners[["X", "Y", "Number", "Angle", "Distance"]].rename(columns=str.lower).to_dict("records"),
            "marshal_sectors": circuit_info.marshal_sectors[["X", "Y", "Number", "Angle", "Distance"]].rename(columns=str.lower).to_dict("records"),
            "sector_distances": sector_distances,
        }
    except Exception as e:
        return {"available": False, "error": str(e)}

def get_round(year: int, round: int):
    event = fastf1.get_event(year, round)
    sessions = _get_round_sessions(event)

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

def get_round_detailed(year: int, round: int, config: SessionDetailConfig = SessionDetailConfig()):
    event = fastf1.get_event(year, round)
    sessions = _get_round_sessions_detailed(event, year, round, config)

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

def _get_round_sessions(event):
    sessions = []
    for i in range(1, 6):
        name = event.get(f"Session{i}")
        date = event.get(f"Session{i}Date")
        if not name or str(name).strip() == "":
            continue
        identifier = SESSION_NAME_TO_IDENTIFIER.get(name, name)
        status = _event_status(date)
        start_time = str(date.time())[:5] if hasattr(date, "time") else None
        duration = SESSION_DURATION_MINUTES.get(identifier, 60)
        end_dt = date + timedelta(minutes=duration) if hasattr(date, "time") else None
        end_time = str(end_dt.time())[:5] if end_dt else None

        sessions.append({
            "name": name,
            "identifier": identifier,
            "date": str(date.date()) if hasattr(date, "date") else str(date),
            "start_time": start_time,
            "end_time": end_time,
            "status": status,
        })
    return sessions

def _get_round_sessions_detailed(event, year: int, round: int, config: SessionDetailConfig):
    sessions = []
    for i in range(1, 6):
        name = event.get(f"Session{i}")
        date = event.get(f"Session{i}Date")
        if not name or str(name).strip() == "":
            continue
        identifier = SESSION_NAME_TO_IDENTIFIER.get(name, name)
        status = _event_status(date)
        weather = None
        fastest_lap = None
        if status == "completed" and (config.weather or config.laps):
            weather, fastest_lap = _get_session_data(year, round, identifier, config)
        start_time = str(date.time())[:5] if hasattr(date, "time") else None
        duration = SESSION_DURATION_MINUTES.get(identifier, 60)
        end_dt = date + timedelta(minutes=duration) if hasattr(date, "time") else None
        end_time = str(end_dt.time())[:5] if end_dt else None

        sessions.append({
            "name": name,
            "identifier": identifier,
            "date": str(date.date()) if hasattr(date, "date") else str(date),
            "start_time": start_time,
            "end_time": end_time,
            "status": status,
            "weather": weather,
            "fastest_lap": fastest_lap,
        })
    return sessions


def _get_session_data(year: int, round: int, identifier: str, config: SessionDetailConfig):
    try:
        session = fastf1.get_session(year, round, identifier)
        session.load(laps=config.laps, telemetry=False, messages=False, weather=config.weather)

        weather = None
        w = session.weather_data if config.weather else None
        if w is not None and not w.empty:
            weather = {
                "air_temp": round_val(w["AirTemp"].mean()),
                "track_temp": round_val(w["TrackTemp"].mean()),
                "humidity": round_val(w["Humidity"].mean()),
                "wind_speed": round_val(w["WindSpeed"].mean()),
                "rainfall": bool(w["Rainfall"].any()),
            }

        fastest_lap = None
        if config.laps and session.laps is not None:
            lap = session.laps.pick_fastest()
            try:
                if lap is not None:
                    td = pd.Timedelta(lap["LapTime"])
                    total = td.total_seconds()
                    minutes = int(total // 60)
                    seconds = total % 60
                    fastest_lap = f"{minutes}:{seconds:06.3f}"
            except Exception as e:
                print(f"Error in _get_session_data trying to format lap time: {e}")
                return None, None

        return weather, fastest_lap
    except Exception as e:
        print(f"Error in _get_session_data: {e}")
        return None, None

def _event_status(date):
    if date is None:
        return "unknown"
    now = datetime.now(timezone.utc)
    event_date = date if isinstance(date, datetime) else datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc)
    if event_date.tzinfo is None:
        event_date = event_date.replace(tzinfo=timezone.utc)
    return "upcoming" if event_date > now else "completed"

def round_val(val):
    try:
        return round(float(val), 1)
    except Exception:
        return None


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
