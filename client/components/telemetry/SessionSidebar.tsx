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
import { Driver, SelectedLap, Team } from "@/lib/types";
import { Skeleton } from "../ui/skeleton";
import { cn } from "@/lib/utils";
import { useSchedule } from "@/lib/hooks/useSchedule";
import { useRoundSchedule } from "@/lib/hooks/useRoundSchedule";
import { useSessionLaps } from "@/lib/hooks/useSessionLaps";
import { lapTimeToMs } from "@/lib/format";
import {
  ensureSameCircuit,
  isLapSelected,
  parseSelectedLaps,
  serializeSelectedLaps,
} from "@/lib/selectedLaps";
import { useQueryClient } from "@tanstack/react-query";

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
  const queryClient = useQueryClient();
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

  const { driverLaps, isLoading: isLoadingLaps, fetchingDrivers} = useSessionLaps(year, round, session, selectedDrivers);

  const compareFastestLaps = async () => {
    const byCode = new Map(driverLaps.map((d) => [d.abbreviation, d]));
    const existing = parseSelectedLaps(searchParams.get("laps") ?? "");

    const proceed = (base: SelectedLap[]) => {
      const merged = [...base];
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
        if (bestNum === null) continue;
        const entry = { year, round, session, driver: code, lap: bestNum };
        if (!isLapSelected(merged, entry)) merged.push(entry);
      }
      if (!merged.length) return;
      const params = new URLSearchParams(searchParams.toString());
      params.set("laps", serializeSelectedLaps(merged));
      params.set("tab", "telemetry");
      router.push(pathname + "?" + params.toString());
    };

    if (await ensureSameCircuit(queryClient, existing, { year, round, session }, proceed)) {
      proceed(existing);
    }
  };

  return (
    <div className="shrink-0 flex flex-col">
      <div className="py-1 flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <span className="font-mono text-[9px] font-semibold tracking-[0.25em] uppercase text-data-blue">
            01 · Year
          </span>
        <Select
          value={year}
          onValueChange={(val) =>
            router.push(pathname + "?" + createQueryString("year", val))
          }
        >
          <SelectTrigger className="w-full rounded-none font-mono text-xs text-text-primary border-surface-border bg-surface-card">
            <SelectValue placeholder="Select year" />
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
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="font-mono text-[9px] font-semibold tracking-[0.25em] uppercase text-data-violet">
            02 · Event
          </span>
        <Select
          value={round}
          disabled={isLoadingSchedule}
          onValueChange={(val) =>
            router.push(pathname + "?" + createQueryString("round", val))
          }
        >
          <SelectTrigger className="w-full rounded-none font-mono text-xs text-text-primary border-surface-border bg-surface-card">
            <SelectValue placeholder="Select event" />
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
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="font-mono text-[9px] font-semibold tracking-[0.25em] uppercase text-data-amber">
            03 · Session
          </span>
        <Select
          value={session}
          disabled={isLoadingRound}
          onValueChange={(val) =>
            router.push(pathname + "?" + createQueryString("session", val))
          }
        >
          <SelectTrigger className="w-full rounded-none font-mono text-xs text-text-primary border-surface-border bg-surface-card">
            <SelectValue placeholder="Select session" />
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
                    disabled={s.status !== "completed"}
                  >
                    {s.name}
                  </SelectItem>
                );
              })}
            </SelectGroup>
          </SelectContent>
        </Select>
        </div>
      </div>
      {(loadingSession || teams.length > 0) && (
        <span className="font-mono text-[9px] font-semibold tracking-[0.25em] uppercase text-data-cyan pt-4 pb-1">
          04 · Drivers
        </span>
      )}
      <div className="flex-1 overflow-y-auto py-2 grid gap-x-2 gap-y-2.5 content-start">
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
                  <span className="font-mono text-[9px] text-text-muted uppercase tracking-[0.18em] mb-1 block truncate">
                    {team.name}
                  </span>
                  <div className="flex gap-1">
                    {team?.drivers.map((d: Driver) => {
                      if (!d) return;
                      const active = selectedDrivers.includes(d.abbreviation);
                      const loading = fetchingDrivers.has(d.abbreviation);
                      return (
                        <button
                          type="button"
                          key={d.abbreviation}
                          onClick={() => toggleDriver(d.abbreviation)}
                          disabled={!d.participated}
                          aria-pressed={active}
                          aria-busy={loading}
                          className={cn(
                            "flex-1 py-1.5 font-mono text-xs font-bold text-center relative overflow-hidden transition-colors border border-surface-border",
                            d.participated
                              ? "cursor-pointer hover:border-text-disabled"
                              : "cursor-not-allowed opacity-60 line-through",
                            active ? "text-black border-transparent" : "text-text-muted",
                          )}
                        >
                          <span
                            className={cn(
                              "absolute left-0 top-0 bottom-0 transition-[width] duration-300 ease-in-out",
                              loading && "driver-fill-pulse",
                            )}
                            style={{
                              width: active ? "100%" : "3px",
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
      <div className="flex flex-col gap-2 pt-4">
        <button
          type="button"
          onClick={compareFastestLaps}
          disabled={selectedDrivers.length === 0 || isLoadingLaps}
          className="cursor-pointer w-full py-2.5 font-mono text-[10px] font-semibold uppercase tracking-[0.2em] bg-accent-green hover:bg-accent-green-hover text-black transition-colors [clip-path:polygon(0_0,100%_0,100%_calc(100%-10px),calc(100%-10px)_100%,0_100%)] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-accent-green"
        >
          {isLoadingLaps ? "Loading laps…" : "Compare fastest laps →"}
        </button>
        <button
          type="button"
          className="cursor-pointer w-full py-2.5 font-mono text-[10px] font-semibold uppercase tracking-[0.2em] border border-surface-border bg-surface-card hover:bg-surface-card-hover text-text-secondary hover:text-text-primary transition-colors"
          onClick={clearDrivers}
        >
          Clear drivers
        </button>
      </div>
    </div>
  );
}
