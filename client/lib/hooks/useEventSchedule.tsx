import { useQuery } from "@tanstack/react-query";
import { fetchEventSchedule } from "../api";

export function useEventSchedule(year: string, event: string) {
  return useQuery({
    queryKey: ["eventSchedule", year, event],
    queryFn: () => fetchEventSchedule(year, event),
    enabled: !!year && !!event,
    placeholderData: (previousData) => previousData,
  });
}
