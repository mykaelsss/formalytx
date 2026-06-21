import axios from "axios";
import { CircuitInfo, DriverLaps, EventSchedule, LapTelemetry, Schedule, TelemetrySession } from "./types";

const api = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000",
});

export async function fetchSession(year: string, event: string, session: string) {
    const res = await api.get<TelemetrySession>(`/sessions/${year}/${event}/${session}`)
    return res.data;
}

export async function fetchSessionLaps(year: string, event: string, session: string, drivers: string) {
    const res = await api.get<DriverLaps[]>(`/sessions/${year}/${event}/${session}/laps`, {
        params: {
            drivers
        }
    })
    return res.data;
}

export async function fetchCircuit(year: string, event: string) {
    const res = await api.get<CircuitInfo>(`/schedule/${year}/${event}/circuit`);
    return res.data;
}

export async function fetchSchedule(year: string) {
    const res = await api.get<Schedule>(`/schedule/${year}`)
    return res.data;
}

export async function fetchEventSchedule(year: string, event: string) {
    const res = await api.get<EventSchedule>(`/schedule/${year}/${event}`)
    return res.data;
}

export async function fetchLapTelemetry(year: string, event: string, session: string, selected_laps: string) {
    const res = await api.get<LapTelemetry[]>(`/sessions/${year}/${event}/${session}/laps/telemetry`, {
        params: {
            selected_laps
        }
    })
    return res.data;
}