"use client";

import { useMemo, useState } from "react";
import { m } from "motion/react";
import SessionViewer from "./SessionViewer";
import TelemetryViewer from "./TelemetryViewer";
import { parseSelectedLaps } from "@/lib/selectedLaps";
import { useLapTelemetry } from "@/lib/hooks/useLapTelemetry";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
import { Button } from "../ui/button";
import { Share } from "lucide-react";
import { toast } from "sonner";
import { useSession } from "@/lib/hooks/useSession";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";
import { useQueryState } from "nuqs";
import { DEFAULT_NUQS_OPTIONS } from "@/lib/constants";

interface TelemetryTabsProps {
  activeTab: string;
}

const tabs = [
  { value: "session", label: "Session" },
  { value: "telemetry", label: "Telemetry" },
];

export default function TelemetryTabs({
  activeTab: initialTab,
}: TelemetryTabsProps) {
  const [year] = useQueryState("year", DEFAULT_NUQS_OPTIONS);
  const [event] = useQueryState("event", DEFAULT_NUQS_OPTIONS);
  const [session] = useQueryState("session", DEFAULT_NUQS_OPTIONS);
  const [laps] = useQueryState("laps", DEFAULT_NUQS_OPTIONS);
  const [tab, setTab] = useQueryState("tab", {
    ...DEFAULT_NUQS_OPTIONS,
    defaultValue: initialTab,
  });

const [visitedTabs, setVisitedTabs] = useState<Set<string>>(
    new Set([tab]),
  );

  const [initialLaps] = useState(laps);
  const [hasInteracted, setHasInteracted] = useState(false);
  if (!hasInteracted && laps !== initialLaps) setHasInteracted(true);

  const selectedLaps = useMemo(() => parseSelectedLaps(laps), [laps]);
  useLapTelemetry(selectedLaps, hasInteracted || visitedTabs.has("telemetry"));

  if (!visitedTabs.has(tab)) {
    setVisitedTabs((prev) => new Set(prev).add(tab));
  }
  const [isSharing, setIsSharing] = useState(false);

  const { data: sessionData, isFetching: isLoadingSession } = useSession(
    year,
    event,
    session,
  );

  const handleShare = async () => {
    if (isSharing) return;

    if (navigator.share) {
      try {
        setIsSharing(true);
        await navigator.share({
          title: `${sessionData?.name} • ${sessionData?.event_name} ${year}`,
          url: window.location.href,
        });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        toast("There was an error sharing this link.");
        console.error(err);
      } finally {
        setIsSharing(false);
      }
    } else {
      try {
        await navigator.clipboard.writeText(window.location.href);
        toast("Copied", {
          description: `${sessionData?.name} • ${sessionData?.event_name} ${year}`,
        });
      } catch {
        toast("There was an error copying this link.");
      }
    }
  };
  const handleTabChange = (val: string) => {
    setVisitedTabs((prev) => new Set(prev).add(val));
    setTab(val)
  };

  return (
    <Tabs
      value={tab}
      onValueChange={handleTabChange}
      className="px-3 sm:px-5 mx-auto max-w-400 py-6 gap-0"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2.5 border-b border-surface-border font-mono text-[10px] tracking-[0.2em] uppercase text-text-muted">
        <span>FRMLX // Explorer</span>
        {sessionData ? (
          <span className="flex items-center gap-2 text-text-secondary">
            <span className="size-1.5 rounded-full bg-accent-green shrink-0 animate-pulse" />
            {sessionData.event_name} · {sessionData.name} · {year}
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <span className="size-1.5 rounded-full bg-surface-border shrink-0" />
            No session loaded
          </span>
        )}
      </div>

      <div className="flex items-center justify-between gap-3 border-b border-surface-border">
        <TabsList className="bg-transparent p-0 h-auto! gap-0 rounded-none">
          {tabs.map((t, i) => (
            <TabsTrigger
              key={t.value}
              value={t.value}
              className="relative flex-none rounded-none border-0 px-3 sm:px-6 py-4 font-mono text-[11px] font-semibold tracking-[0.2em] uppercase text-text-muted bg-transparent! data-active:text-accent-green transition-colors cursor-pointer hover:text-text-primary"
            >
              <span className="text-[9px] text-text-disabled tabular-nums">
                0{i + 1}
              </span>
              {t.label}
              {tab === t.value && (
                <m.span
                  layoutId="tab-underline"
                  className="absolute inset-x-0 -bottom-px h-0.5 bg-accent-green"
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
            </TabsTrigger>
          ))}
        </TabsList>
        <Tooltip>
          <TooltipTrigger asChild>
            <span>
              <Button
                className="rounded-none h-9 px-3 sm:px-4 font-mono text-[11px] font-semibold tracking-[0.15em] uppercase text-accent-green cursor-pointer border border-surface-border bg-surface-card hover:bg-surface-card-hover"
                onClick={handleShare}
                disabled={!sessionData || isSharing || isLoadingSession}
              >
                <Share className="size-3.5!" /> Share
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="text-sm">
            {sessionData
              ? "Share a link to this session view"
              : "Select a session to share"}
          </TooltipContent>
        </Tooltip>
      </div>
      {visitedTabs.has("session") && (
        <TabsContent
          value="session"
          forceMount
          hidden={tab !== "session"}
          className="pt-6"
        >
          <SessionViewer />
        </TabsContent>
      )}
      {visitedTabs.has("telemetry") && (
        <TabsContent
          value="telemetry"
          forceMount
          hidden={tab !== "telemetry"}
          className="pt-6"
        >
          <TelemetryViewer />
        </TabsContent>
      )}
    </Tabs>
  );
}
