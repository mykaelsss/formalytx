import { useMemo, useState } from "react";
import type { CircuitInfo, LapTelemetry } from "../types";
import { fastestLap } from "../delta";
import { seriesKey } from "../seriesKey";
import { buildSeries } from "../buildSeries";

export function useTelemetrySeries(
  telemetryData: LapTelemetry[],
  circuitData: CircuitInfo | undefined,
  hiddenSeries: Set<string>,
  colorSlots: Record<string, number>,
) {
  const fastestVisible = useMemo(() => {
    const visibleLaps = telemetryData.filter(
      (lap) => !hiddenSeries.has(seriesKey(lap.driver, lap.lap_number)),
    );
    return visibleLaps.length > 0 ? fastestLap(visibleLaps) : null;
  }, [telemetryData, hiddenSeries]);

  const [lastVisible, setLastVisible] = useState<LapTelemetry | null>(null);
  if (fastestVisible && fastestVisible !== lastVisible) {
    setLastVisible(fastestVisible);
  }

  const refLap =
    fastestVisible ??
    (telemetryData.length > 0 ? (lastVisible ?? fastestLap(telemetryData)) : null);

  return useMemo(
    () => buildSeries(telemetryData, refLap, circuitData, colorSlots),
    [telemetryData, circuitData, refLap, colorSlots],
  );
}
