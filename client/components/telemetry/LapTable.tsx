import { Compound, Lap, Team } from "@/lib/types";
import TireBadge from "./TireBadge";
import { Skeleton } from "../ui/skeleton";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { cn } from "@/lib/utils";
import { useSessionLaps } from "@/lib/hooks/useSessionLaps";
import { toggleLap, parseSelectedLaps } from "@/lib/selectedLaps";
import { lapTimeToMs } from "@/lib/format";

function formatDelta(ms: number): string {
  return `+${(ms / 1000).toFixed(3)}`;
}

interface LapTableProps {
  teams: Team[];
}

export default function LapTable({ teams }: LapTableProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
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

  const lapQueries = useSessionLaps(year, round, session, selectedDrivers);

  const driverLaps = lapQueries.flatMap((q) => q.data ?? []);
  const isLoadingLaps = lapQueries.some((q) => q.isLoading);

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

  return (
    <>
      <div className="flex flex-col w-full text-xs overflow-y-auto max-h-125">
        {lapsByNumber.map(({ lapNumber, entries, fastest }) => (
          <div key={lapNumber} className="border-b border-surface-border">
            <div className="flex items-center justify-between px-3 py-1.5 bg-surface-border/30">
              <span className="font-bold tracking-widest text-text-secondary uppercase">
                Lap {String(lapNumber).padStart(2, "0")}
              </span>
              <span className="text-text-muted text-[10px] tracking-wider uppercase">
                INTERVAL
              </span>
            </div>
            {entries.map(({ abbreviation, lap }) => {
              const driver = driverMap.get(abbreviation);
              const color = `#${driver?.team_color ?? "888888"}`;
              const ms = lapTimeToMs(lap.lap_time);
              const isFastestOverall = ms !== null && ms === overallFastest;
              const isDriverBest =
                ms !== null && ms === driverFastest.get(abbreviation);
              const deltaMs =
                ms !== null && fastest !== Infinity ? ms - fastest : null;
              const isInvalid = lap.lap_time === null;
              return (
                <button
                  type="button"
                  key={abbreviation}
                  className={cn(
                    "w-full text-left flex items-center gap-3 px-3 py-2 border-b border-surface-border/40 last:border-0 cursor-pointer hover:bg-surface-card-hover transition-colors",
                    isFastestOverall && "bg-purple-950/20",
                    isDriverBest && !isFastestOverall && "bg-green-950/20",
                    isInvalid && "opacity-40",
                  )}
                  onClick={() =>
                    toggleLap(selectedLaps, abbreviation, lapNumber, {
                      router,
                      pathname: window.location.pathname,
                      searchParams,
                    })
                  }
                >
                  <span
                    className="size-2 rounded-full"
                    style={{ background: color }}
                  ></span>
                  <span className="font-bold w-8 shrink-0" style={{ color }}>
                    {abbreviation}
                  </span>
                  <TireBadge
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
                  {isFastestOverall ? (
                    <span className="text-purple-400 font-bold text-[10px] tracking-wider">
                      BEST
                    </span>
                  ) : isDriverBest ? (
                    <span className="text-green-400 font-bold text-[10px] tracking-wider">
                      PB
                    </span>
                  ) : deltaMs !== null && deltaMs > 0 ? (
                    <span className="text-text-muted font-mono tabular-nums">
                      {formatDelta(deltaMs)}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        ))}
        {isLoadingLaps && (
          <div className="border-b border-surface-border">
            <div className="flex items-center justify-between px-3 py-1.5 bg-surface-card/50">
              <Skeleton className="h-3 w-12 bg-text-disabled" />
            </div>
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 px-3 py-2">
                <Skeleton className="size-5 rounded-full bg-text-disabled" />
                <Skeleton className="h-3 w-8 bg-text-disabled" />
                <Skeleton className="h-3 w-20 bg-text-disabled" />
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
