"use client";

import {
  Dispatch,
  SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import LapTable from "./LapTable";
import SessionSidebar from "./SessionSidebar";
import { motion } from "motion/react";
import { Driver, DriverLaps, Team, TelemetrySession } from "@/lib/types";
import axios from "axios";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import LapChart from "./LapChart";
import { cn } from "@/lib/utils";
import { useSession } from "@/lib/hooks/useSession";
import { useSessionLaps } from "@/lib/hooks/useSessionLaps";

export default function SessionViewer() {
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

  const { data: sessionData, isLoading: isLoadingSession } = useSession(year, round, session);

  const [sidebarOpen, setSidebarOpen] = useState(true);

  const teams = useMemo(() => {
    if (!sessionData) return []
    const teamMap = new Map<string, Team>()
    for (const d of sessionData.drivers) {
      if (!teamMap.has(d.team_name)) {
        teamMap.set(d.team_name, { name: d.team_name, color: d.team_color, drivers: [] })
      }
      teamMap.get(d.team_name)!.drivers.push(d)
    }
    return Array.from(teamMap.values())
  }, [sessionData])

  const createQueryString = useCallback(
    (name: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set(name, value);

      return params.toString();
    },
    [searchParams],
  );

  useEffect(() => {
    if (teams.length === 0) return;
    const validAbbrevs = new Set(
      teams
        .flatMap((t) => t.drivers)
        .filter((d) => d.participated)
        .map((d) => d.abbreviation),
    );
    const validDrivers = selectedDrivers.filter((a) => validAbbrevs.has(a));
    if (validDrivers.length !== selectedDrivers.length) {
      router.replace(
        pathname + "?" + createQueryString("drivers", validDrivers.join(",")),
      );
    }
  }, [teams, router, pathname, createQueryString, selectedDrivers]);

  return (
    <div className={cn(
      "border border-surface-border bg-surface-base flex flex-col lg:flex-row items-start min-h-120 py-8 px-4 rounded-xs",
      sidebarOpen ? "gap-4" : "max-lg:gap-4"
      )}>
      <motion.div
        animate={{
          width: sidebarOpen ? 208 : 0,
          opacity: sidebarOpen ? 1 : 0,
        }}
        transition={{ type: "tween", duration: 0.35, ease: "easeInOut" }}
        className={cn(
          "max-lg:w-full! max-lg:opacity-100! overflow-hidden lg:border-r lg:border-surface-border",
          sidebarOpen && "lg:pr-4",
        )}
      >
        <SessionSidebar loadingSession={isLoadingSession} teams={teams} />
      </motion.div>
      <div className="flex-1 w-full flex flex-col min-w-0 gap-4 overflow-hidden">
        <button
          onClick={() => setSidebarOpen((o) => !o)}
          className="self-start text-text-muted hover:text-text-primary transition-colors text-xs hidden lg:inline cursor-pointer"
        >
          {sidebarOpen ? "← Hide" : "→ Show"}
        </button>
        <LapChart teams={teams} />
        <LapTable
          teams={teams}
        />
      </div>
    </div>
  );
}
