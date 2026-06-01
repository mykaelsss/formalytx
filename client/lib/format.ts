import type { Channel } from "./constants";
import type { Corner } from "./types";

export function getCornerLabel(corners: Corner[], dist: number): string {
  if (!corners.length) return `${Math.round(dist)} m`;

  // corners arrive ordered by distance around the lap, so binary-search the
  // first corner at/after `dist`; the nearest is that one or its predecessor.
  let lo = 0;
  let hi = corners.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (corners[mid]!.distance < dist) lo = mid + 1;
    else hi = mid;
  }
  let closest = corners[lo]!;
  const prev = corners[lo - 1];
  if (
    prev &&
    Math.abs(prev.distance - dist) <= Math.abs(closest.distance - dist)
  ) {
    closest = prev;
  }

  const offset = Math.round(dist - closest.distance);
  if (Math.abs(offset) <= 30) return `Corner ${closest.number}`;
  return offset > 0
    ? `Corner ${closest.number} +${offset}m`
    : `Corner ${closest.number} ${offset}m`;
}



export function formatLapTime(seconds: number | null): string {
  if (seconds === null) return "—";
  const totalMs = Math.round(seconds * 1000);
  const mins = Math.floor(totalMs / 60000);
  const secs = (totalMs % 60000) / 1000;
  return `${mins}:${secs.toFixed(3).padStart(6, "0")}`;
}

export function formatChannelVal(channel: Channel, val: number): string {
  if (channel === "delta") return `${val > 0 ? "+" : ""}${val.toFixed(3)}s`;
  if (channel === "brake") return val === 1 ? "ON" : "OFF";
  if (channel === "throttle") return `${Math.round(val)}%`;
  if (channel === "speed") return `${Math.round(val)} km/h`;
  if (channel === "rpm") return Math.round(val).toLocaleString();
  return `${Math.round(val)}`;
}