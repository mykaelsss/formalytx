import { useQueries, type UseQueryResult } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import { fetchLapTelemetry } from "../api";
import type { LapTelemetry } from "../types";

type FailedLap = {
  driver: string;
  lap: number;
  refetch: UseQueryResult<LapTelemetry[], Error>["refetch"];
};

export function useLapTelemetry(
  year: string,
  round: string,
  session: string,
  selectedLaps: Map<string, number[]>,
  enabled: boolean = true,
): {
  data: LapTelemetry[];
  isPending: boolean;
  failed: FailedLap[];
  pending: { driver: string; lap: number }[];
} {
  const entries = useMemo(
    () =>
      Array.from(selectedLaps.entries()).flatMap(([driver, laps]) =>
        laps.map((lap) => ({ driver, lap })),
      ),
    [selectedLaps],
  );

  const combine = useCallback(
    (results: UseQueryResult<LapTelemetry[], Error>[]) => ({
      data: results.flatMap((r) => r.data ?? []),
      isPending: results.some((r) => r.isPending),
      failed: entries.reduce<FailedLap[]>((acc, entry, i) => {
        if (results[i]?.isError) acc.push({ ...entry, refetch: results[i]!.refetch });
        return acc;
      }, []),
      pending: entries.filter((_, i) => results[i]?.isPending),
    }),
    [entries],
  );

  return useQueries({
    queries: entries.map(({ driver, lap }) => ({
      queryKey: ["lapTelemetry", year, round, session, driver, lap],
      queryFn: () => fetchLapTelemetry(year, round, session, `${driver}:${lap}`),
      enabled: enabled && !!year && !!round && !!session,
    })),
    combine,
  });
}
