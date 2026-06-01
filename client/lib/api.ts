import axios from "axios";
import { CircuitInfo, DriverLaps, LapTelemetry, RoundSchedule, Schedule, TelemetrySession } from "./types";

export async function fetchSession(year: string, round: string, session: string) {
    const res = await axios.get<TelemetrySession>(`http://127.0.0.1:8000/sessions/${year}/${round}/${session}`)
    return res.data;
}

export async function fetchSessionLaps(year: string, round: string, session: string, drivers: string) {
    const res = await axios.get<DriverLaps[]>(`http://127.0.0.1:8000/sessions/${year}/${round}/${session}/laps`, {
        params: {
            drivers
        }
    })
    return res.data;
}

export async function fetchCircuit(year: string, round: string) {
    const res = await axios.get<CircuitInfo>(`http://127.0.0.1:8000/schedule/${year}/${round}/circuit`);
    return res.data;
}

export async function fetchSchedule(year: string) {
    const res = await axios.get<Schedule>(`http://127.0.0.1:8000/schedule/${year}`)
    return res.data;
}

export async function fetchRoundSchedule(year: string, round: string) {
    const res = await axios.get<RoundSchedule>(`http://127.0.0.1:8000/schedule/${year}/${round}`)
    return res.data;
}

export async function fetchLapTelemetry(year: string, round: string, session: string, selected_laps: string) {
    const res = await axios.get<LapTelemetry[]>(`http://127.0.0.1:8000/sessions/${year}/${round}/${session}/laps/telemetry`, {
        params: {
            selected_laps
        }
    })
    return res.data;
}