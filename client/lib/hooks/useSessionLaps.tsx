import { useQueries, UseQueryResult } from "@tanstack/react-query";
import { fetchSessionLaps } from "../api";
import { useCallback } from "react";
import { DriverLaps } from "../types";

export function useSessionLaps(
  year: string,
  event: string,
  session: string,
  drivers: string[],
  staleTime: number = Infinity,
): {
  driverLaps: DriverLaps[],
  isLoading: boolean,
  fetchingDrivers: Set<string>
} {
  const combine = useCallback(
    (results: UseQueryResult<DriverLaps[], Error>[]) => ({
      driverLaps: results.flatMap((r) => r.data ?? []),
      isLoading: results.some((r) => r.isLoading),
      fetchingDrivers: new Set(drivers.filter((_, i) => results[i]?.isFetching)),
    }),
    [drivers],
  );

  return useQueries({
    queries: drivers.map((driver) => ({
      queryKey: ["sessionLaps", year, event, session, driver],
      queryFn: () => fetchSessionLaps(year, event, session, driver),
      enabled: !!year && !!event && !!session && !!driver,
      staleTime,
    })),
    combine
  });
}