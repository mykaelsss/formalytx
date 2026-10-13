import { parseAsArrayOf, useQueryState } from "nuqs";
import { parseAsQualiSession, VALID_QUALI_SESSIONS } from "../constants";
import type { QualiSession } from "../types";

const ALL_QUALI_SESSIONS: QualiSession[] = [...VALID_QUALI_SESSIONS];

/**
 * The qualifying segments shown for Q and SQ sessions: all of them unless the
 * URL narrows them down. Other sessions ignore it.
 */
export function useQualiSessions() {
  return useQueryState(
    "qualiSessions",
    parseAsArrayOf(parseAsQualiSession)
      .withDefault(ALL_QUALI_SESSIONS)
      .withOptions({ scroll: false }),
  );
}
