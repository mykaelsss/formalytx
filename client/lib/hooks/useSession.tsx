import { useQuery } from "@tanstack/react-query";
import { fetchSession } from "../api";

export function useSession(year: string, event: string, session: string) {
  return useQuery({
    queryKey: ["session", year, event, session],
    queryFn: () => fetchSession(year, event, session),
    enabled: !!year && !!event && !!session,
    placeholderData: (previousData) => previousData,
  });
}
