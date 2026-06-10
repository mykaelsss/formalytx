import { useMemo, useState } from "react";
import type { CircuitInfo, LapTelemetryWithSession } from "../types";
import { fastestLap } from "../delta";
import { seriesKey, telemetryToSelected } from "../seriesKey";
import { buildSeries } from "../buildSeries";

export function useTelemetrySeries(
  telemetryData: LapTelemetryWithSession[],
  circuitData: CircuitInfo | undefined,
  hiddenSeries: Set<string>,
  colorSlots: Record<string, number>,
) {
  const fastestVisible = useMemo(() => {
    const visibleLaps = telemetryData.filter(
      (lap) => !hiddenSeries.has(seriesKey(telemetryToSelected(lap))),
    );
    return visibleLaps.length > 0 ? fastestLap(visibleLaps) : null;
  }, [telemetryData, hiddenSeries]);

  const [lastVisible, setLastVisible] = useState<LapTelemetryWithSession | null>(null);
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
