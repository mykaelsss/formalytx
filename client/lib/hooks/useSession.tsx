import { useQuery } from "@tanstack/react-query";
import { fetchSession } from "../api";

export function useSession(year: string, round: string, session: string) {
  return useQuery({
    queryKey: ["session", year, round, session],
    queryFn: () => fetchSession(year, round, session),
    enabled: !!year && !!round && !!session,
    placeholderData: (previousData, previousQuery) => previousData,
  });
}
