"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import { useCallback, useMemo } from "react";
import { Driver, Team } from "@/lib/types";
import { Skeleton } from "../ui/skeleton";
import { cn } from "@/lib/utils";
import { useSchedule } from "@/lib/hooks/useSchedule";
import { useRoundSchedule } from "@/lib/hooks/useRoundSchedule";
import { useSessionLaps } from "@/lib/hooks/useSessionLaps";
import { lapTimeToMs } from "@/lib/format";

const YEARS = Array.from({ length: new Date().getFullYear() - 2017 }, (_, i) =>
  String(new Date().getFullYear() - i),
);

interface SessionSidebarProps {
  loadingSession: boolean;
  teams: Team[];
}

export default function SessionSidebar({
  loadingSession,
  teams,
}: SessionSidebarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const year = searchParams.get("year") ?? "";
  const round = searchParams.get("round") ?? "";
  const session = searchParams.get("session") ?? "";
  const drivers = searchParams.get("drivers") ?? "";

  const selectedDrivers = useMemo(
      () => (drivers ? drivers.split(",") : []),
      [drivers],
    );

  const { data: schedule, isLoading: isLoadingSchedule } = useSchedule(year);
  const { data: roundSchedule, isLoading: isLoadingRound } = useRoundSchedule(year, round);

  const createQueryString = useCallback(
    (name: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set(name, value);

      return params.toString();
    },
    [searchParams],
  );

  const toggleDriver = useCallback(
    (code: string) => {
      const next = new Set(selectedDrivers);
      if (next.has(code)) {
        next.delete(code);
      } else {
        next.add(code);
      }
      router.replace(
        pathname +
          "?" +
          createQueryString("drivers", Array.from(next).join(",")),
        { scroll: false },
      );
    },
    [selectedDrivers, pathname, createQueryString, router],
  );

  const clearDrivers = () => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("drivers");
    router.replace(pathname + "?" + params.toString(), { scroll: false });
  };

  const lapQueries = useSessionLaps(year, round, session, selectedDrivers);
  const driverLaps = lapQueries.flatMap((q) => q.data ?? []);
  const isLoadingLaps = lapQueries.some((q) => q.isLoading);

  const compareFastestLaps = () => {
    const byCode = new Map(driverLaps.map((d) => [d.abbreviation, d]));
    const entries: string[] = [];
    for (const code of selectedDrivers) {
      const dl = byCode.get(code);
      if (!dl) continue;
      let bestNum: number | null = null;
      let bestMs = Infinity;
      for (const lap of dl.laps) {
        const ms = lapTimeToMs(lap.lap_time);
        if (ms !== null && lap.lap_number !== null && ms < bestMs) {
          bestMs = ms;
          bestNum = lap.lap_number;
        }
      }
      if (bestNum !== null) entries.push(`${code}:${bestNum}`);
    }
    if (!entries.length) return;
    const params = new URLSearchParams(searchParams.toString());
    params.set("laps", entries.join("|"));
    params.set("tab", "telemetry");
    router.push(pathname + "?" + params.toString());
  };

  return (
    <div className="shrink-0 flex flex-col">
      <div className="py-3 flex flex-col gap-2">
        <Select
          value={year}
          onValueChange={(val) =>
            router.push(pathname + "?" + createQueryString("year", val))
          }
        >
          <SelectTrigger className="w-full text-text-primary border-surface-border">
            <SelectValue placeholder="Year" />
          </SelectTrigger>
          <SelectContent
            side="bottom"
            position="popper"
            className="bg-surface-card max-h-60"
          >
            <SelectGroup>
              <SelectLabel>Year</SelectLabel>
              {YEARS.map((y) => {
                return (
                  <SelectItem key={y} className="text-text-primary" value={y}>
                    {y}
                  </SelectItem>
                );
              })}
            </SelectGroup>
          </SelectContent>
        </Select>
        <Select
          value={round}
          disabled={isLoadingSchedule}
          onValueChange={(val) =>
            router.push(pathname + "?" + createQueryString("round", val))
          }
        >
          <SelectTrigger className="w-full text-text-primary border-surface-border">
            <SelectValue placeholder="Schedule" />
          </SelectTrigger>
          <SelectContent
            side="bottom"
            position="popper"
            className="bg-surface-card max-h-60"
          >
            <SelectGroup>
              <SelectLabel>Schedule</SelectLabel>
              {schedule?.rounds.map((r, idx) => {
                return (
                  <SelectItem
                    key={idx}
                    className="text-text-primary"
                    value={r.round.toString()}
                  >
                    {r.event_name}
                  </SelectItem>
                );
              })}
            </SelectGroup>
          </SelectContent>
        </Select>
        <Select
          value={session}
          disabled={isLoadingRound}
          onValueChange={(val) =>
            router.push(pathname + "?" + createQueryString("session", val))
          }
        >
          <SelectTrigger className="w-full text-text-primary border-surface-border">
            <SelectValue placeholder="Session" />
          </SelectTrigger>
          <SelectContent
            side="bottom"
            position="popper"
            className="bg-surface-card max-h-60"
          >
            <SelectGroup>
              <SelectLabel>Session</SelectLabel>
              {roundSchedule?.sessions.map((s) => {
                return (
                  <SelectItem
                    key={s.identifier}
                    className="text-text-primary"
                    value={s.identifier}
                  >
                    {s.name}
                  </SelectItem>
                );
              })}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>
      <div className="flex-1 overflow-y-auto py-2 grid gap-x-2 gap-y-2 content-start">
        {loadingSession
          ? Array.from({ length: 10 }).map((_, idx) => (
              <div key={idx}>
                <Skeleton className="h-2 w-12 mb-1 rounded-none bg-text-disabled" />
                <div className="flex gap-1">
                  <Skeleton className="h-6 w-10 rounded-none flex-1 bg-text-disabled" />
                  <Skeleton className="h-6 w-10 rounded-none flex-1 bg-text-disabled" />
                </div>
              </div>
            ))
          : teams.map((team) => {
              return (
                <div key={team.name} className="animate-in fade-in-5 duration-1000">
                  <span className="text-[10px] text-text-primary uppercase tracking-widest mb-0.5 block truncate">
                    {team.name}
                  </span>
                  <div className="flex gap-1">
                    {team?.drivers.map((d: Driver) => {
                      if (!d) return;
                      const active = selectedDrivers.includes(d.abbreviation);
                      return (
                        <button
                          type="button"
                          key={d.abbreviation}
                          onClick={() => toggleDriver(d.abbreviation)}
                          disabled={!d.participated}
                          className={cn("flex-1 py-1 text-xs font-bold text-center relative overflow-hidden transition-colors",
                            (d.participated) ? 'cursor-pointer' : 'cursor-not-allowed opacity-80 line-through'
                          )}
                          style={{ color: active ? "#000" : "#555" }}
                        >
                          <span
                            className="absolute left-0 top-0 bottom-0 transition-[width] duration-300 ease-in-out"
                            style={{
                              width: active ? "100%" : "2px",
                              background: `#${team.color}`,
                            }}
                          />
                          <span className="relative z-10">
                            {d.abbreviation}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
      </div>
      <div className="flex flex-col gap-2 pt-3">
        <button
          type="button"
          onClick={compareFastestLaps}
          disabled={selectedDrivers.length === 0 || isLoadingLaps}
          className="cursor-pointer w-full py-2 text-xs font-bold uppercase tracking-widest bg-surface-card hover:bg-surface-card-hover text-text-secondary transition-colors rounded-md disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-surface-card"
        >
          {isLoadingLaps ? "Loading laps…" : "Compare fastest laps"}
        </button>
        <button
          type="button"
          className="cursor-pointer w-full py-2 text-xs font-bold uppercase tracking-widest bg-surface-card hover:bg-surface-card-hover text-text-secondary transition-colors rounded-md"
          onClick={clearDrivers}
        >
          Clear Drivers
        </button>
      </div>
    </div>
  );
}
