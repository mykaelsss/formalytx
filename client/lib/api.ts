import axios from "axios";
import { CircuitInfo, DriverLaps, LapTelemetry, RoundSchedule, Schedule, TelemetrySession } from "./types";

const api = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000",
});

export async function fetchSession(year: string, round: string, session: string) {
    const res = await api.get<TelemetrySession>(`/sessions/${year}/${round}/${session}`)
    return res.data;
}

export async function fetchSessionLaps(year: string, round: string, session: string, drivers: string) {
    const res = await api.get<DriverLaps[]>(`/sessions/${year}/${round}/${session}/laps`, {
        params: {
            drivers
        }
    })
    return res.data;
}

export async function fetchCircuit(year: string, round: string) {
    const res = await api.get<CircuitInfo>(`/schedule/${year}/${round}/circuit`);
    return res.data;
}

export async function fetchSchedule(year: string) {
    const res = await api.get<Schedule>(`/schedule/${year}`)
    return res.data;
}

export async function fetchRoundSchedule(year: string, round: string) {
    const res = await api.get<RoundSchedule>(`/schedule/${year}/${round}`)
    return res.data;
}

export async function fetchLapTelemetry(year: string, round: string, session: string, selected_laps: string) {
    const res = await api.get<LapTelemetry[]>(`/sessions/${year}/${round}/${session}/laps/telemetry`, {
        params: {
            selected_laps
        }
    })
    return res.data;
}