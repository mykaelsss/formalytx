import { useQueries } from "@tanstack/react-query";
import { fetchSessionLaps } from "../api";

export function useSessionLaps(
  year: string,
  round: string,
  session: string,
  drivers: string[],
) {
  return useQueries({
    queries: drivers.map((driver) => ({
      queryKey: ["sessionLaps", year, round, session, driver],
      queryFn: () => fetchSessionLaps(year, round, session, driver),
      enabled: !!year && !!round && !!session && !!driver,
    })),
  });
}