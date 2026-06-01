import { Compound, DriverLaps, Lap, Team } from "@/lib/types";
import TireBadge from "./TireBadge";
import { Skeleton } from "../ui/skeleton";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { cn } from "@/lib/utils";
import { getCompoundColor } from "@/lib/compounds";
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
  const pathname = usePathname();
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

  const maxLaps = useMemo(() => {
    if (!visibleLaps.length) return null;
    return Math.max(...visibleLaps.map((d) => d.laps.length));
  }, [visibleLaps]);

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
        const sorted = [...entries].sort((a, b) => {
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
                <div
                  key={abbreviation}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 border-b border-surface-border/40 last:border-0 cursor-pointer hover:bg-surface-card-hover transition-colors",
                    isFastestOverall && "bg-purple-950/20",
                    isDriverBest && !isFastestOverall && "bg-green-950/20",
                    isInvalid && "opacity-40",
                  )}
                  onClick={() =>
                    toggleLap(selectedLaps, abbreviation, lapNumber, {
                      router,
                      pathname,
                      searchParams,
                    })
                  }
                >
                  <span
                    className="h-2 w-2 rounded-full"
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
                </div>
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
                <Skeleton className="h-5 w-5 rounded-full bg-text-disabled" />
                <Skeleton className="h-3 w-8 bg-text-disabled" />
                <Skeleton className="h-3 w-20 bg-text-disabled" />
              </div>
            ))}
          </div>
        )}
      </div>
      {/* <div className="overflow-x-auto w-full border-collapse border border-surface-border">
      <table className="text-xs max-w-full w-full">
        <thead>
          <tr className="border-b border-surface-border">
            {selectedDrivers.length > 0 && (
              <>
                {maxLaps && (
                  <th className="px-3 py-2 text-text-muted font-bold uppercase tracking-widest bg-surface-base w-16 sticky left-0 z-10">
                    Laps
                  </th>
                )}
                {Array.from({ length: maxLaps ?? 0 }).map((_, idx) => {
                  return (
                    <th
                      key={idx}
                      className="py-2 text-text-muted text-center tabular-nums"
                    >
                      {idx + 1}
                    </th>
                  );
                })}
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {visibleLaps.map((d, idx) => {
            const driver = driverMap.get(d.abbreviation);
            return (
              <tr key={idx} className="border-b border-surface-border/80">
                <td
                  className="text-center font-bold sticky left-0 z-10 bg-surface-card/90"
                  style={{ color: `#${driver?.team_color}` }}
                >
                  <span>{driver?.abbreviation}</span>
                </td>
                {d.laps.map((lap, idx) => {
                  const color = getCompoundColor(
                    (lap.compound as Compound) ?? "HARD",
                    year,
                  );
                  return (
                    <td key={idx} className="px-3 py-2">
                      <div
                        className="inline-flex items-center justify-center gap-1.5 px-3 has-[>svg]:px-2.5 h-8 rounded-[10px] border font-medium"
                        style={{
                          backgroundColor: `color-mix(in oklch, ${color}, transparent 85%)`,
                          borderColor: `color-mix(in oklch, ${color}, transparent 75%)`,
                        }}
                      >
                        <TireBadge
                          compound={
                            (lap.compound?.toUpperCase() ?? "HARD") as Compound
                          }
                          size={22}
                          year={year}
                        />
                        <span className="text-text-primary font-mono tabular-nums">
                          {lap.lap_time ?? "N/A"}
                        </span>
                      </div>
                    </td>
                  );
                })}
              </tr>
            );
          })}
          {loadingLaps && (
            <tr className="border-b border-surface-border/80">
              <td className="min-w-14.25">
                <Skeleton className="w-6 h-3.5 rounded-[2.2px] bg-text-disabled mx-auto" />
              </td>
              <td colSpan={(maxLaps ?? 3) + 1} className="px-3 py-2">
                <div className="inline-flex items-center gap-2">
                  {Array.from({
                    length: Math.min(maxLaps ?? 3, 10),
                  }).map((_, i) => (
                    <Skeleton key={i} className="h-8 w-24 bg-text-disabled" />
                  ))}
                </div>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div> */}
    </>
  );
}
