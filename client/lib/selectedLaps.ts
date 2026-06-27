import type { QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  consumeLapAwaitingReview,
  lapAddedToast,
  markLapAwaitingReview,
} from "./toasts";
import { seriesKey } from "./seriesKey";
import { fetchSession } from "./api";
import type { SelectedLap } from "./types";
import { Options } from "nuqs";

export function parseSelectedLaps(laps: string): SelectedLap[] {
  const selected: SelectedLap[] = [];
  const seen = new Set<string>();
  for (const entry of laps.split("|")) {
    const [year, event, session, driver, lapsStr] = entry.split(":");
    if (!year || !event || !session || !driver || !lapsStr) continue;
    const lapNumbers = lapsStr.split(",").map(Number)
    const uniqueLapNumbers = Array.from((new Set(lapNumbers)))
    for (const n of uniqueLapNumbers) {
      if (!Number.isInteger(n) || n <= 0) continue;
      const lap = { year, event, session, driver, lap: n };
      const key = seriesKey(lap);
      if (seen.has(key)) continue;
      seen.add(key);
      selected.push(lap);
    }
  }
  return selected;
}

export function serializeSelectedLaps(selected: SelectedLap[]): string | null {
  if (!selected.length) return null;

  const groups = new Map<string, number[]>();
  for (const l of selected) {
    const gk = `${l.year}:${l.event}:${l.session}:${l.driver}`;
    const laps = groups.get(gk);
    if (laps) laps.push(l.lap);
    else groups.set(gk, [l.lap]);
  }
  return Array.from(groups.entries())
    .map(([gk, laps]) => `${gk}:${laps.join(",")}`)
    .join("|");
}

export function isLapSelected(
  selected: SelectedLap[],
  lap: SelectedLap,
): boolean {
  const key = seriesKey(lap);
  return selected.some((l) => seriesKey(l) === key);
}

type SessionContext = { year: string; event: string; session: string };

async function circuitLocation(queryClient: QueryClient, ctx: SessionContext) {
  return queryClient
    .fetchQuery({
      queryKey: ["session", ctx.year, ctx.event, ctx.session],
      queryFn: () => fetchSession(ctx.year, ctx.event, ctx.session),
      staleTime: Infinity,
    })
    .then((data) => data.location);
}

export async function ensureSameCircuit(
  queryClient: QueryClient,
  existing: SelectedLap[],
  ctx: SessionContext,
  onRemoveAndContinue: (sameCircuitLaps: SelectedLap[]) => void,
): Promise<boolean> {
  const otherEvents = new Map<string, SelectedLap>();
  for (const l of existing) {
    if (l.year === ctx.year && l.event === ctx.event) continue;
    otherEvents.set(`${l.year}:${l.event}`, l);
  }
  if (otherEvents.size === 0) return true;
  let mismatched: Set<string>;
  try {
    const target = await circuitLocation(queryClient, ctx);
    const entries = Array.from(otherEvents.entries());
    const locations = await Promise.all(
      entries.map(([, l]) => circuitLocation(queryClient, l)),
    );
    mismatched = new Set(
      entries.filter((_, i) => locations[i] !== target).map(([k]) => k),
    );
  } catch {
    return true;
  }
  if (mismatched.size === 0) return true;
  const kept = existing.filter((l) => !mismatched.has(`${l.year}:${l.event}`));
  toast.error("Laps from different circuits can't be compared", {
    id: "circuit-mismatch",
    className: "border-accent-red! flex-wrap! gap-y-2!",
    classNames: {
      actionButton:
        "basis-full! justify-center! text-center! bg-transparent! border! border-accent-red-dark! text-accent-red-dark! hover:bg-accent-red-dark/10! font-mono uppercase tracking-[0.15em]",
    },
    action: {
      label: "Remove old laps & add this one",
      onClick: () => onRemoveAndContinue(kept),
    },
  });
  return false;
}

type NavCtx = {
  queryClient: QueryClient;
  setLaps: (value: string | ((old: string) => string | null) | null, options?: Options | undefined) => Promise<URLSearchParams>
  setTab: (value: string | ((old: string) => string | null) | null, options?: Options | undefined) => Promise<URLSearchParams>
};

function addLap(
  selected: SelectedLap[],
  lap: SelectedLap,
  { setLaps, setTab }: NavCtx,
) {
  const key = seriesKey(lap);
  setLaps(serializeSelectedLaps([...selected, lap]));

  markLapAwaitingReview(key);
  lapAddedToast(lap.driver, lap.lap, () => setTab('telemetry'));
}

export async function toggleLap(
  selected: SelectedLap[],
  lap: SelectedLap,
  ctx: NavCtx,
) {
  const key = seriesKey(lap);
  const exists = selected.some((l) => seriesKey(l) === key);

  if (exists) {
    const updated = selected.filter((l) => seriesKey(l) !== key);
    ctx.setLaps(serializeSelectedLaps(updated))
    consumeLapAwaitingReview(key);
    return;
  }

  const ok = await ensureSameCircuit(ctx.queryClient, selected, lap, (kept) =>
    addLap(kept, lap, ctx),
  );
  if (ok) addLap(selected, lap, ctx);
}
