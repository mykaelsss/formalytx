import type { Corner, LapTelemetry } from "./types";
import { CHANNELS, SAMPLE_COUNT } from "./constants";
import { sampleLap } from "./interp";
import { formatChannelVal, formatLapTime, getCornerLabel } from "./format";
import { format } from "echarts";

type TooltipContext = {
  nLaps: number;
  corners: Corner[];
  telemetryData: LapTelemetry[];
  commonStart: number;
  commonEnd: number;
  deltaBySeries: Map<string, number[]>;
  refLapName: string;
  refTimes: number[];
  hoveredSeriesRef: { current: number | null };
};

export function buildTooltipFormatter({
  nLaps,
  corners,
  telemetryData,
  commonStart,
  commonEnd,
  deltaBySeries,
  refLapName,
  refTimes,
  hoveredSeriesRef,
}: TooltipContext) {
  const marker = (color: string) =>
    `<span class="inline-block w-5 mr-2 border-t-2" style="border-color:${format.encodeHTML(color)}"></span>`;

  const row = (label: string, val: string) =>
    `<div class="flex justify-between gap-6 text-xs leading-relaxed">` +
    `<span class="text-text-muted">${label}</span>` +
    `<span class="text-text-primary font-mono">${val}</span></div>`;

  const header = (dist: number) => {
    const label = format.encodeHTML(getCornerLabel(corners, dist));
    const total = corners.length ? ` · ${Math.round(dist)} m` : "";
    return `<div class="text-xs text-text-muted mb-1">${label}${total}</div>`;
  };

  return (params: unknown) => {
    const seriesParams = params as Array<{
      seriesIndex: number;
      seriesName: string;
      color: string;
      value: [number, number];
    }>;
    if (!seriesParams?.length) return "";
    const currSeries = seriesParams[0];
    if (!currSeries) return "";
    const currentDistance = currSeries.value[0];
    const channelIdx = Math.floor(currSeries.seriesIndex / nLaps);
    const inGrid = seriesParams.filter(
      (p) => Math.floor(p.seriesIndex / nLaps) === channelIdx,
    );

    // Reset hovered state if cursor moved to a different grid
    const hovered = hoveredSeriesRef.current;
    if (hovered !== null && Math.floor(hovered / nLaps) !== channelIdx) {
      hoveredSeriesRef.current = null;
    }

    const lapIdx =
      hoveredSeriesRef.current !== null
        ? hoveredSeriesRef.current % nLaps
        : null;
    if (lapIdx !== null) {
      const lap = telemetryData[lapIdx];
      if (lap) {
        const s = inGrid.find((p) => p.seriesIndex % nLaps === lapIdx);
        const lapName = s?.seriesName ?? "";
        const minD = commonStart;
        const maxD = commonEnd;
        const deltaLookup = (name: string) => {
          const deltas = deltaBySeries.get(name) ?? [];
          const range = maxD - minD || 1;
          const idx = Math.max(
            0,
            Math.min(
              Math.round(
                ((currentDistance - minD) / range) * (SAMPLE_COUNT - 1),
              ),
              deltas.length - 1,
            ),
          );
          return deltas[idx] ?? 0;
        };
        let html = header(currentDistance);
        html += `<div class="flex items-center text-xs font-semibold text-text-secondary mb-1">${marker(s?.color ?? "#888")}${format.encodeHTML(lapName)}</div>`;
        const isRef = lapName === refLapName;
        const refTimeAtDistance = () => {
          const times = refTimes;
          const idx = Math.max(
            0,
            Math.min(
              Math.round(
                ((currentDistance - minD) / (maxD - minD || 1)) *
                  (SAMPLE_COUNT - 1),
              ),
              times.length - 1,
            ),
          );
          return times[idx] ?? null;
        };
        for (const ch of CHANNELS) {
          if (ch === "delta" && isRef) {
            html += row("elapsed", formatLapTime(refTimeAtDistance()));
          } else {
            const val =
              ch === "delta"
                ? deltaLookup(lapName)
                : sampleLap(lap, ch, currentDistance);
            html += row(ch, formatChannelVal(ch, val));
          }
        }
        return html;
      }
    }

    const channel = CHANNELS[channelIdx];
    // Order laps fastest-to-slowest by overall lap time so the reference lap
    // (fastest) sits at the top and deltas read top-down; laps with no recorded
    // time sort last.
    const ordered = inGrid.toSorted(
      (a, b) =>
        (telemetryData[a.seriesIndex % nLaps]?.lap_time ?? Infinity) -
        (telemetryData[b.seriesIndex % nLaps]?.lap_time ?? Infinity),
    );
    let html = header(currentDistance);
    for (const p of ordered) {
      const isRef = channel === "delta" && p.seriesName === refLapName;
      const valStr = isRef
        ? (() => {
            const times = refTimes;
            const minD = commonStart;
            const maxD = commonEnd;
            const idx = Math.max(
              0,
              Math.min(
                Math.round(
                  ((currentDistance - minD) / (maxD - minD || 1)) *
                    (SAMPLE_COUNT - 1),
                ),
                times.length - 1,
              ),
            );
            return formatLapTime(times[idx] ?? null);
          })()
        : channel && formatChannelVal(channel, p.value[1]);
      html +=
        `<div class="flex justify-between gap-6 text-xs leading-relaxed">` +
        `<div class="flex items-center">${marker(p.color)}<span class="text-text-secondary">${format.encodeHTML(p.seriesName)}</span></div>` +
        `<span class="text-text-primary font-mono">${valStr}</span></div>`;
    }
    return html;
  };
}
