import { Compound, Lap, Team } from "@/lib/types";
import TyreBadge from "./TyreBadge";
import { Skeleton } from "../ui/skeleton";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { cn } from "@/lib/utils";
import { useSessionLaps } from "@/lib/hooks/useSessionLaps";
import { useRoundSchedule } from "@/lib/hooks/useRoundSchedule";
import { toggleLap, parseSelectedLaps, isLapSelected } from "@/lib/selectedLaps";
import { lapTimeToMs } from "@/lib/format";

function formatDelta(ms: number): string {
  return `+${(ms / 1000).toFixed(3)}`;
}

interface LapTableProps {
  teams: Team[];
}

export default function LapTable({ teams }: LapTableProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const year = searchParams.get("year") ?? "";
  const round = searchParams.get("round") ?? "";
  const session = searchParams.get("session") ?? "";
  const drivers = searchParams.get("drivers") ?? "";
  const laps = searchParams.get("laps") ?? "";

  const selectedDrivers = useMemo(
    () => (drivers ? drivers.split(",") : []),
    [drivers],
  );

  const selectedLaps = useMemo(() => parseSelectedLaps(laps), [laps]);

  const { data: roundSchedule } = useRoundSchedule(year, round);
  const sessionStatus = roundSchedule?.sessions.find((s) => s.identifier === session)?.status;
  const staleTime = sessionStatus === "completed" ? Infinity : 60_000;

  const { driverLaps, isLoading: isLoadingLaps } = useSessionLaps(year, round, session, selectedDrivers, staleTime);

  const visibleLaps = useMemo(
    () => driverLaps.filter((d) => selectedDrivers.includes(d.abbreviation)),
    [driverLaps, selectedDrivers],
  );

  const driverMap = useMemo(
    () =>
      new Map(teams.flatMap((t) => t.drivers).map((d) => [d.abbreviation, d])),
    [teams],
  );

  const overallFastest = useMemo(() => {
    const times = visibleLaps
      .flatMap((d) => d.laps.map((l) => lapTimeToMs(l.lap_time)))
      .filter((ms): ms is number => ms !== null);
    return times.length ? Math.min(...times) : null;
  }, [visibleLaps]);

  const driverFastest = useMemo(() => {
    const map = new Map<string, number>();
    for (const d of visibleLaps) {
      const times = d.laps
        .map((l) => lapTimeToMs(l.lap_time))
        .filter((ms): ms is number => ms !== null);
      if (times.length) map.set(d.abbreviation, Math.min(...times));
    }
    return map;
  }, [visibleLaps]);

  const lapsByNumber = useMemo(() => {
    const map = new Map<number, { abbreviation: string; lap: Lap }[]>();
    for (const d of visibleLaps) {
      for (const lap of d.laps) {
        const num = lap.lap_number;
        if (!num) continue;
        if (!map.has(num)) map.set(num, []);
        map.get(num)!.push({ abbreviation: d.abbreviation, lap });
      }
    }
    return Array.from(map.entries())
      .sort(([a], [b]) => a - b)
      .map(([lapNumber, entries]) => {
        const times = entries
          .map((e) => lapTimeToMs(e.lap.lap_time))
          .filter((ms): ms is number => ms !== null);
        const fastest = times.length ? Math.min(...times) : Infinity;
        const sorted = entries.toSorted((a, b) => {
          const aMs = lapTimeToMs(a.lap.lap_time);
          const bMs = lapTimeToMs(b.lap.lap_time);
          if (aMs === null && bMs === null) return 0;
          if (aMs === null) return 1;
          if (bMs === null) return -1;
          return aMs - bMs;
        });
        return { lapNumber, entries: sorted, fastest };
      });
  }, [visibleLaps]);

  const rows = useMemo(() => {
    const out: (
      | { kind: "header"; lapNumber: number }
      | {
          kind: "lap";
          lapNumber: number;
          abbreviation: string;
          lap: Lap;
          fastest: number;
        }
    )[] = [];
    for (const { lapNumber, entries, fastest } of lapsByNumber) {
      out.push({ kind: "header", lapNumber });
      for (const { abbreviation, lap } of entries) {
        out.push({ kind: "lap", lapNumber, abbreviation, lap, fastest });
      }
    }
    return out;
  }, [lapsByNumber]);

  const scrollRef = useRef<HTMLDivElement>(null);
  //directDomUpdates should work with react compiler. Ignore warning for now.
  // eslint-disable-next-line react-hooks/incompatible-library -- opted out of memoization via "use no memo"
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: (i) => (rows[i]?.kind === "header" ? 29 : 37),
    overscan: 5,
    directDomUpdates: true,
  });

  return (
    <div className="w-full border border-surface-border bg-surface-card flex flex-col">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2.5 border-b border-surface-border">
        <span className="font-mono text-[10px] tracking-[0.2em] uppercase text-text-muted">
          Timing sheet
        </span>
        <span className="font-mono text-[9px] tracking-[0.2em] uppercase text-text-muted">
          Click a lap → add to telemetry
        </span>
      </div>
      <div
        ref={scrollRef}
        className="relative w-full text-xs overflow-y-auto max-h-125"
      >
        <div
          ref={virtualizer.containerRef}
          className="relative w-full"
        >
          {virtualizer.getVirtualItems().map((vi) => {
            const item = rows[vi.index];
            if (!item) return null;
            return (
              <div
                key={vi.key}
                data-index={vi.index}
                ref={virtualizer.measureElement}
                className="absolute left-0 top-0 w-full"
                style={{ transform: `translateY(${vi.start}px)` }}
              >
                {item.kind === "header" ? (
                  <div className="flex items-center justify-between px-4 py-1.5 bg-surface-border/30 border-b border-surface-border">
                    <span className="font-mono font-bold text-[10px] tracking-[0.2em] text-text-secondary uppercase tabular-nums">
                      Lap {String(item.lapNumber).padStart(2, "0")}
                    </span>
                    <span className="font-mono text-text-muted text-[9px] tracking-[0.2em] uppercase">
                      Interval
                    </span>
                  </div>
                ) : (
                  (() => {
                    const { abbreviation, lap, lapNumber, fastest } = item;
                    const driver = driverMap.get(abbreviation);
                    const color = `#${driver?.team_color ?? "888888"}`;
                    const ms = lapTimeToMs(lap.lap_time);
                    const isFastestOverall = ms !== null && ms === overallFastest;
                    const isDriverBest =
                      ms !== null && ms === driverFastest.get(abbreviation);
                    const deltaMs =
                      ms !== null && fastest !== Infinity ? ms - fastest : null;
                    const isInvalid = lap.lap_time === null;
                    const isOnChart = isLapSelected(selectedLaps, {
                      year,
                      round,
                      session,
                      driver: abbreviation,
                      lap: lapNumber,
                    });
                    return (
                      <button
                        type="button"
                        aria-pressed={isOnChart}
                        className={cn(
                          "group relative w-full text-left flex items-center gap-3 px-4 py-2 border-b border-surface-border/40 last:border-0 cursor-pointer hover:bg-surface-card-hover transition-colors",
                          isFastestOverall && "bg-data-violet/10",
                          isDriverBest && !isFastestOverall && "bg-accent-green/5",
                          isInvalid && "opacity-40",
                        )}
                        onClick={() =>
                          toggleLap(
                            selectedLaps,
                            {
                              year,
                              round,
                              session,
                              driver: abbreviation,
                              lap: lapNumber,
                            },
                            {
                              router,
                              pathname: pathname,
                              searchParams,
                              queryClient,
                            },
                          )
                        }
                      >
                        {isOnChart && (
                          <span className="absolute left-0 top-0 bottom-0 w-0.5 bg-accent-green" />
                        )}
                        <span
                          className="size-2 rounded-full shrink-0"
                          style={{ background: color }}
                        ></span>
                        <span
                          className="font-mono font-bold w-9 shrink-0"
                          style={{ color }}
                        >
                          {abbreviation}
                        </span>
                        <TyreBadge
                          compound={
                            (lap.compound?.toUpperCase() ?? "HARD") as Compound
                          }
                          size={20}
                          year={year}
                        />
                        <span
                          className={cn(
                            "flex-1 font-mono tabular-nums",
                            isInvalid
                              ? "text-text-disabled text-[10px]"
                              : "text-text-primary",
                          )}
                        >
                          {lap.lap_time ?? "—"}
                        </span>
                        <span
                          className={cn(
                            "font-mono text-[9px] tracking-[0.15em] w-14 text-right shrink-0 transition-opacity max-sm:hidden",
                            isOnChart
                              ? "text-accent-green"
                              : "text-text-muted opacity-0 group-hover:opacity-100",
                          )}
                        >
                          {isOnChart ? "● ADDED" : "+ ADD"}
                        </span>
                        {isFastestOverall ? (
                          <span className="text-data-violet font-mono font-bold text-[10px] tracking-[0.15em]">
                            BEST
                          </span>
                        ) : isDriverBest ? (
                          <span className="text-accent-green font-mono font-bold text-[10px] tracking-[0.15em]">
                            PB
                          </span>
                        ) : null}
                        {deltaMs !== null && deltaMs > 0 && (
                          <span className="text-text-muted font-mono tabular-nums">
                            {formatDelta(deltaMs)}
                          </span>
                        )}
                      </button>
                    );
                  })()
                )}
              </div>
            );
          })}
        </div>
        {!isLoadingLaps && lapsByNumber.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-2 py-14 text-center px-4">
            <span className="font-mono text-[10px] tracking-[0.25em] uppercase text-text-muted">
              No laps loaded
            </span>
            <p className="text-sm text-text-secondary max-w-xs">
              Select a session and drivers to populate the timing sheet.
            </p>
          </div>
        )}
        {isLoadingLaps && (
          <div className="border-b border-surface-border">
            <div className="flex items-center justify-between px-4 py-1.5 bg-surface-card/50">
              <Skeleton className="h-3 w-12 bg-text-disabled" />
            </div>
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-2">
                <Skeleton className="size-5 rounded-full bg-text-disabled" />
                <Skeleton className="h-3 w-8 bg-text-disabled" />
                <Skeleton className="h-3 w-20 bg-text-disabled" />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
