import { interp } from "./interp";
import { LapTelemetry } from "./types";


export function computeDelta(
  lap: LapTelemetry,
  ref: LapTelemetry,
  refDist: number[],
): number[] {
  if (refDist.length === 0) return [];

  const lapD0 = lap.channels.distance[0] ?? 0;
  const lapD1 = lap.channels.distance.at(-1) ?? 1;
  const lapT0 = lap.channels.time[0] ?? 0;
  const lapSpan = (lap.channels.time.at(-1) ?? 0) - lapT0;
  const lapFactor = lapSpan > 0 && lap.lap_time ? lap.lap_time / lapSpan : 1;

  const refD0 = ref.channels.distance[0] ?? 0;
  const refD1 = ref.channels.distance.at(-1) ?? 1;
  const refT0 = ref.channels.time[0] ?? 0;
  const refSpan = (ref.channels.time.at(-1) ?? 0) - refT0;
  const refFactor = refSpan > 0 && ref.lap_time ? ref.lap_time / refSpan : 1;

  const d0 = refDist[0] ?? 0;
  const d1 = refDist.at(-1) ?? 1;
  const span = d1 - d0 || 1;

  return refDist.map((d) => {
    const frac = (d - d0) / span;
    const lapT =
      (interp(
        lapD0 + frac * (lapD1 - lapD0),
        lap.channels.distance,
        lap.channels.time,
      ) -
        lapT0) *
      lapFactor;
    const refT =
      (interp(
        refD0 + frac * (refD1 - refD0),
        ref.channels.distance,
        ref.channels.time,
      ) -
        refT0) *
      refFactor;
    return Math.round((lapT - refT) * 1000) / 1000;
  });
}

export function fastestLap(laps: LapTelemetry[]): LapTelemetry {
  return laps.reduce((best, lap) => {
    const t = lap.lap_time ?? Infinity;
    const bt = best.lap_time ?? Infinity;
    return t < bt ? lap : best;
  });
}