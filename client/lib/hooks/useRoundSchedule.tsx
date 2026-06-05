import { useQuery } from "@tanstack/react-query";
import { fetchRoundSchedule } from "../api";

export function useRoundSchedule(year: string, round: string) {
  return useQuery({
    queryKey: ["roundSchedule", year, round],
    queryFn: () => fetchRoundSchedule(year, round),
    enabled: !!year && !!round,
    placeholderData: (previousData) => previousData,
  });
}
