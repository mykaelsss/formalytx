import { TelemetryChannel } from "./constants";
import type { LapTelemetry } from "./types";

export function linspace(start: number, stop: number, num: number): number[] {
  if (!Number.isInteger(num) || num < 0) {
    throw new Error("num must be a non-negative integer");
  }
  if (num === 0) return [];
  if (num === 1) return [start];
  const step = (stop - start) / (num - 1);
  const result = Array.from({ length: num }, (_, i) => start + i * step);
  result[num - 1] = stop; // guarantee exact endpoint
  return result;
}

export function sampleLap(
  lap: LapTelemetry,
  channel: TelemetryChannel,
  dist: number,
): number {
  const xp = lap.channels.distance;
  if (channel === "brake") {
    const fp = lap.channels.brake.map((b) => (b ? 1 : 0));
    return interp(dist, xp, fp) >= 0.5 ? 1 : 0;
  }
  const fp =
    channel === "speed"
      ? lap.channels.speed
      : channel === "throttle"
        ? lap.channels.throttle
        : channel === "rpm"
          ? lap.channels.rpm
          : lap.channels.gear;
  const val = interp(dist, xp, fp);
  return channel === "gear" ? Math.round(val) : val;
}


export function interp(
  x: number,
  xp: number[],
  fp: number[],
  left?: number,
  right?: number,
): number {
  const n = xp.length;
  if (n === 0) throw new Error("interp: empty xp array");
  if (n !== fp.length) throw new Error("interp: xp and fp length mismatch");

  if (x <= xp[0]!) return left ?? fp[0]!;
  if (x >= xp[n - 1]!) return right ?? fp[n - 1]!;

  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xp[mid]! <= x) lo = mid;
    else hi = mid;
  }

  const x0 = xp[lo]!;
  const x1 = xp[hi]!;
  const f0 = fp[lo]!;
  const f1 = fp[hi]!;

  if (x1 === x0) return f0;
  return f0 + ((x - x0) / (x1 - x0)) * (f1 - f0);
}
