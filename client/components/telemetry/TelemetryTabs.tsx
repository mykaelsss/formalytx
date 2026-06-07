"use client";

import { useCallback, useMemo,  useState } from "react";
import { m } from "motion/react";
import SessionViewer from "./SessionViewer";
import TelemetryViewer from "./TelemetryViewer";
import { useRouter, useSearchParams } from "next/navigation";
import { parseSelectedLaps } from "@/lib/selectedLaps";
import { useLapTelemetry } from "@/lib/hooks/useLapTelemetry";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
import { Button } from "../ui/button";
import { Share } from "lucide-react";
import { toast } from "sonner";
import { useSession } from "@/lib/hooks/useSession";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "../ui/tooltip";

interface TelemetryTabsProps {
  activeTab: string;
}

const tabs = [
  { value: "session", label: "Session" },
  { value: "telemetry", label: "Telemetry" },
];

export default function TelemetryTabs({ activeTab: initialTab }: TelemetryTabsProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const year = searchParams.get("year") ?? "";
  const round = searchParams.get("round") ?? "";
  const session = searchParams.get("session") ?? "";
  const laps = searchParams.get("laps") ?? "";
  // Drive the live tab off client searchParams, not the server prop: a prod
  // build serves searchParam-only soft navs from the router cache without
  // re-running the server component, so the prop would stay frozen until reload.
  const activeTab = searchParams.get("tab") ?? initialTab;

  const [visitedTabs, setVisitedTabs] = useState<Set<string>>(
    new Set([activeTab]),
  );

  const [initialLaps] = useState(laps);
  const [hasInteracted, setHasInteracted] = useState(false);
  if (!hasInteracted && laps !== initialLaps) setHasInteracted(true);

  const selectedLaps = useMemo(() => parseSelectedLaps(laps), [laps]);
  useLapTelemetry(
    year,
    round,
    session,
    selectedLaps,
    hasInteracted || visitedTabs.has("telemetry"),
  );

  if (!visitedTabs.has(activeTab)) {
    setVisitedTabs((prev) => new Set(prev).add(activeTab));
  }
  const [isSharing, setIsSharing] = useState(false);

  const { data: sessionData, isFetching: isLoadingSession } = useSession(
    year,
    round,
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
      await navigator.clipboard.writeText(window.location.href);
      toast("Copied", {
        description: `${sessionData?.name} • ${sessionData?.event_name} ${year}`,
      });
    }
  };

  const handleTabChange = (val: string) => {
    setVisitedTabs((prev) => new Set(prev).add(val));
    router.replace(window.location.pathname + "?" + createQueryString("tab", val));
  };

  const createQueryString = useCallback(
    (name: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set(name, value);

      return params.toString();
    },
    [searchParams],
  );

  return (
    <Tabs
      value={activeTab}
      onValueChange={handleTabChange}
      className="px-2 mx-auto max-w-400 py-8"
    >
      <div className="flex items-end justify-between">
        <TabsList className="relative flex rounded-xs bg-surface-card border border-white/10 p-1 gap-0 mt-10 h-10! min-w-1/4">
          {tabs.map((tab) => (
            <TabsTrigger
              key={tab.value}
              value={tab.value}
              className="relative z-10 p-6 text-text-primary/50 bg-none! data-active:bg-none data-active:text-accent-green transition-colors cursor-pointer hover:text-text-primary"
            >
              {activeTab === tab.value && (
                <m.div
                  layoutId="tab-bg"
                  className="absolute inset-2 rounded-sm border border-accent-green/40"
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
        <Tooltip>
          <TooltipTrigger asChild>
            <span>
              <Button
                className="rounded-xs px-4 text-accent-green cursor-pointer h-10 border border-surface-border bg-surface-card"
                onClick={handleShare}
                disabled={!sessionData || isSharing || isLoadingSession}
              >
                <Share /> Share
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="text-sm">
            {sessionData ? "Share a link to this session view" : "Select a session to share"}
          </TooltipContent>
        </Tooltip>
      </div>
      {visitedTabs.has("session") && (
        <TabsContent
          value="session"
          forceMount
          hidden={activeTab !== "session"}
        >
          <SessionViewer />
        </TabsContent>
      )}
      {visitedTabs.has("telemetry") && (
        <TabsContent
          value="telemetry"
          forceMount
          hidden={activeTab !== "telemetry"}
        >
          <TelemetryViewer />
        </TabsContent>
      )}
    </Tabs>
  );
}
