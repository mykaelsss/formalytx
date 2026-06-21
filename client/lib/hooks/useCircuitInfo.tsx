import { useQuery } from "@tanstack/react-query";
import { fetchCircuit } from "../api";

export function useCircuitInfo(year: string, event: string) {
  return useQuery({
    queryKey: ["circuit", year, event],
    queryFn: () => fetchCircuit(year, event),
    enabled: !!year && !!event,
    placeholderData: (previousData) => previousData,
  });
}