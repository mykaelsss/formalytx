import type { CircuitInfo, LapTelemetry } from "./types";
import { CHANNELS, SAMPLE_COUNT } from "./constants";
import { lapColor } from "./colors";
import { interp, linspace, sampleLap } from "./interp";
import { computeDelta } from "./delta";
import { seriesKey } from "./seriesKey";

function emptyTelemetry(error: string | null) {
  return {
    series: [],
    markLineSeries: [],
    legendItems: [],
    deltaBySeries: new Map<string, number[]>(),
    commonStart: 0,
    commonEnd: 0,
    refLapName: "",
    refTimes: [] as number[],
    error,
  };
}

export function buildSeries(
  telemetryData: LapTelemetry[],
  refLap: LapTelemetry | null,
  circuitData: CircuitInfo | undefined,
  colorSlots: Record<string, number> = {},
) {
  if (telemetryData.length === 0 || !refLap) {
    return emptyTelemetry(null);
  }

  const ref = refLap;
  const refLapName = seriesKey(ref.driver, ref.lap_number);

  // Common distance range: latest start, earliest end, so every lap has real data across the range
  const starts = telemetryData
    .map((lap) => lap.channels.distance[0])
    .filter((d): d is number => d !== undefined);
  const ends = telemetryData
    .map((lap) => lap.channels.distance.at(-1))
    .filter((d): d is number => d !== undefined);
  if (
    starts.length !== telemetryData.length ||
    ends.length !== telemetryData.length
  ) {
    return emptyTelemetry("Telemetry is missing distance data");
  }
  const commonStart = Math.max(...starts);
  const commonEnd = Math.min(...ends);

  if (commonStart >= commonEnd) {
    return emptyTelemetry(
      "Selected laps don't share an overlapping distance range",
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

  const lapEntries = telemetryData.map((lap, i) => {
    const name = seriesKey(lap.driver, lap.lap_number);
    return { lap, name, color: lapColor(colorSlots[name] ?? i) };
  });

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
  }));

  return {
    series,
    markLineSeries,
    legendItems,
    deltaBySeries,
    commonStart,
    commonEnd,
    refLapName,
    refTimes,
    error: null,
  };
}
