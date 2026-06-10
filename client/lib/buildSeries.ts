import type { CircuitInfo, LapTelemetryWithSession, SelectedLap } from "./types";
import { CHANNELS, SAMPLE_COUNT } from "./constants";
import { lapColor } from "./colors";
import { interp, linspace, sampleLap } from "./interp";
import { computeDelta } from "./delta";
import { seriesKey, telemetryToSelected } from "./seriesKey";

function emptyTelemetry(error: string | null, excluded: SelectedLap[] = []) {
  return {
    series: [],
    markLineSeries: [],
    legendItems: [],
    labelBySeries: new Map<string, string>(),
    deltaBySeries: new Map<string, number[]>(),
    commonStart: 0,
    commonEnd: 0,
    refLapName: "",
    refTimes: [] as number[],
    excluded,
    error,
  };
}

export function buildSeries(
  telemetryData: LapTelemetryWithSession[],
  refLap: LapTelemetryWithSession | null,
  circuitData: CircuitInfo | undefined,
  colorSlots: Record<string, number> = {},
) {
  if (telemetryData.length === 0 || !refLap) {
    return emptyTelemetry(null);
  }

  const ref = refLap;
  const refLapName = seriesKey(telemetryToSelected(ref));

  const ranges = telemetryData.map((lap) => ({
    lap,
    start: lap.channels.distance[0],
    end: lap.channels.distance.at(-1),
  }));
  if (ranges.some((r) => r.start === undefined || r.end === undefined)) {
    return emptyTelemetry("Telemetry is missing distance data");
  }

  // Keep as many laps as possible that share a common distance range. Among
  // overlapping intervals, the largest mutually-overlapping set is the one
  // covering the most-stabbed point, so we test each lap's start as a candidate
  // stab point and keep every lap covering the best one. Candidates are clamped
  // into the reference lap's range so the reference is always kept (delta is
  // computed against it). Non-overlapping laps are excluded from the comparison
  // instead of collapsing the range and failing every lap.
  const refStart = ref.channels.distance[0]!;
  const refEnd = ref.channels.distance.at(-1)!;
  const intervals = ranges.map((r) => ({
    lap: r.lap,
    start: r.start!,
    end: r.end!,
  }));

  const covers = (iv: { start: number; end: number }, x: number) =>
    iv.start <= x && iv.end >= x;

  const candidates = new Set<number>([refStart]);
  for (const iv of intervals) {
    if (iv.start >= refStart && iv.start <= refEnd) candidates.add(iv.start);
  }

  let stab = refStart;
  let bestCount = -1;
  for (const x of candidates) {
    const count = intervals.reduce((n, iv) => n + (covers(iv, x) ? 1 : 0), 0);
    if (count > bestCount) {
      bestCount = count;
      stab = x;
    }
  }

  const kept: LapTelemetryWithSession[] = [];
  const excluded: SelectedLap[] = [];
  for (const iv of intervals) {
    if (covers(iv, stab)) kept.push(iv.lap);
    else excluded.push(telemetryToSelected(iv.lap));
  }

  const commonStart = Math.max(...kept.map((l) => l.channels.distance[0]!));
  const commonEnd = Math.min(...kept.map((l) => l.channels.distance.at(-1)!));

  if (kept.length === 0 || commonEnd <= commonStart) {
    return emptyTelemetry(
      "Selected laps don't share an overlapping distance range",
      excluded,
    );
  }

  const refDist = linspace(commonStart, commonEnd, SAMPLE_COUNT);

  const sectorDistances = circuitData?.sector_distances ?? [];
  const sectorData =
    sectorDistances.length >= 2
      ? [
          { name: "S2", xAxis: sectorDistances[0] },
          { name: "S3", xAxis: sectorDistances[1] },
        ]
      : [];

  const perGridMarkLineData = [
    ...(circuitData?.corners ?? []).map((c) => ({
      name: `${c.number}`,
      xAxis: c.distance,
      label: {
        show: true,
        position: "start" as const,
        formatter: "{b}",
        color: "#555",
        fontSize: 10,
      },
      lineStyle: { type: "dashed" as const, color: "#333", width: 1 },
    })),
    ...sectorData.map((s) => ({
      name: s.name,
      xAxis: s.xAxis,
      label: {
        show: true,
        position: "end" as const,
        formatter: s.name,
        color: "#ccc",
        fontSize: 11,
        fontWeight: "bold" as const,
      },
      lineStyle: { type: "solid" as const, color: "#888", width: 2 },
    })),
  ];

  const lapEntries = kept.map((lap, i) => {
    const name = seriesKey(telemetryToSelected(lap));
    return { lap, name, color: lapColor(colorSlots[name] ?? i) };
  });

  // Tooltip labels: driver + lap is enough while every plotted lap comes from
  // one session; once sessions mix, the label must say which event each lap
  // belongs to or identical driver/lap pairs become indistinguishable.
  const singleSession =
    new Set(kept.map((l) => `${l.year}:${l.round}:${l.session}`)).size <= 1;
  const labelBySeries = new Map(
    lapEntries.map(({ lap, name }) => [
      name,
      singleSession
        ? `${lap.driver} - Lap ${lap.lap_number}`
        : `${lap.driver} - Lap ${lap.lap_number} · ${lap.year} R${lap.round} ${lap.session}`,
    ]),
  );

  const deltaBySeries = new Map<string, number[]>();
  for (const { lap, name } of lapEntries) {
    deltaBySeries.set(name, computeDelta(lap, ref, refDist));
  }

  const refT0 = ref.channels.time[0] ?? 0;
  const refSpan = (ref.channels.time.at(-1) ?? 0) - refT0;
  const refFactor = refSpan > 0 && ref.lap_time ? ref.lap_time / refSpan : 1;
  const refTimes = refDist.map(
    (d) =>
      (interp(d, ref.channels.distance, ref.channels.time) - refT0) *
      refFactor,
  );

  const markLineSeries = CHANNELS.map((_, channelIdx) => ({
    type: "line" as const,
    id: `__markline_${channelIdx}`,
    name: `__markline_${channelIdx}`,
    xAxisIndex: channelIdx,
    yAxisIndex: channelIdx,
    data: [] as [number, number][],
    silent: true,
    legendHoverLink: false,
    markLine: { silent: true, symbol: "none", data: perGridMarkLineData },
  }));

  const series = CHANNELS.flatMap((channel, channelIdx) =>
    lapEntries.map(({ lap, name, color }) => {
      let data: [number, number][];
      if (channel === "delta") {
        const deltas = deltaBySeries.get(name) ?? [];
        data = refDist.map((dist, i) => [dist, deltas[i] ?? 0]);
      } else {
        data = refDist.map((dist) => [
          dist,
          Math.round(sampleLap(lap, channel, dist)),
        ]);
      }

      return {
        // Stable, unique id so replaceMerge matches series across updates and
        // only removed laps exit — without it ECharts re-creates every series
        // (name alone repeats per channel), replaying the full enter animation.
        id: `${channelIdx}:${name}`,
        type: "line" as const,
        name,
        color,
        xAxisIndex: channelIdx,
        yAxisIndex: channelIdx,
        data,
        ...(channel === "gear" && { step: "end" as const }),
        ...(channel === "brake" && { step: "end" as const }),
      };
    }),
  );

  const legendItems = lapEntries.map(({ name, color, lap }) => ({
    key: name,
    color,
    driver: lap.driver,
    lap: lap.lap_number,
    lapTime: lap.lap_time,
    compound: lap.compound ?? null,
    tyreLife: lap.tyre_life ?? null,
    year: lap.year,
    round: lap.round,
    session: lap.session,
  }));

  return {
    series,
    markLineSeries,
    legendItems,
    labelBySeries,
    deltaBySeries,
    commonStart,
    commonEnd,
    refLapName,
    refTimes,
    excluded,
    error: null,
  };
}
