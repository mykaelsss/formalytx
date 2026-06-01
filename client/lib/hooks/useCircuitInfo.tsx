import { useQuery } from "@tanstack/react-query";
import { fetchCircuit } from "../api";

export function useCircuitInfo(year: string, round: string) {
  return useQuery({
    queryKey: ["circuit", year, round],
    queryFn: () => fetchCircuit(year, round),
    enabled: !!year && !!round,
    placeholderData: (previousData, previousQuery) => previousData,
  });
}