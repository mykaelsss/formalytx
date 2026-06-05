import { useQuery } from "@tanstack/react-query";
import { fetchSchedule } from "../api";

export function useSchedule(year: string) {
  return useQuery({
    queryKey: ["schedule", year],
    queryFn: () => fetchSchedule(year),
    enabled: !!year,
    placeholderData: (previousData) => previousData,
  });
}
