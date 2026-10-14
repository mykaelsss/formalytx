import { useQuery } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { fetchCircuit } from "../api";

// Some events have no circuit info (e.g. a circuit FastF1 has no layout for),
// which the API answers with a 404. Charts then go without corner markers and
// sector lines, so there's nothing to retry.
export function useCircuitInfo(year: string, event: string) {
  return useQuery({
    queryKey: ["circuit", year, event],
    queryFn: () => fetchCircuit(year, event),
    enabled: !!year && !!event,
    placeholderData: (previousData) => previousData,
    retry: (failureCount, error) =>
      !(isAxiosError(error) && error.response?.status === 404) && failureCount < 1,
  });
}
