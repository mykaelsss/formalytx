import { useQueries, type UseQueryResult } from "@tanstack/react-query";
import { useCallback } from "react";
import { fetchLapTelemetry } from "../api";
import type {
  LapTelemetry,
  LapTelemetryWithSession,
  SelectedLap,
} from "../types";

type FailedLap = SelectedLap & {
  refetch: UseQueryResult<LapTelemetry[], Error>["refetch"];
};

export function useLapTelemetry(
  selectedLaps: SelectedLap[],
  enabled: boolean = true,
): {
  data: LapTelemetryWithSession[];
  isPending: boolean;
  failed: FailedLap[];
  pending: SelectedLap[];
} {
  const combine = useCallback(
    (results: UseQueryResult<LapTelemetry[], Error>[]) => ({
      data: results.flatMap((r, i) => {
        const entry = selectedLaps[i];
        if (!entry) return [];
        return (r.data ?? []).map((lap) => ({
          ...lap,
          year: entry.year,
          round: entry.round,
          session: entry.session,
        }));
      }),
      isPending: results.some((r) => r.isPending),
      failed: selectedLaps.reduce<FailedLap[]>((acc, entry, i) => {
        if (results[i]?.isError)
          acc.push({ ...entry, refetch: results[i]!.refetch });
        return acc;
      }, []),
      pending: selectedLaps.filter((_, i) => results[i]?.isPending),
    }),
    [selectedLaps],
  );

  return useQueries({
    queries: selectedLaps.map((l) => ({
      queryKey: ["lapTelemetry", l.year, l.round, l.session, l.driver, l.lap],
      queryFn: () =>
        fetchLapTelemetry(l.year, l.round, l.session, `${l.driver}:${l.lap}`),
      enabled,
    })),
    combine,
  });
}
