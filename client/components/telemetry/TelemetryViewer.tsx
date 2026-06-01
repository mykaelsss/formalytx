"use client";

import { useLapTelemetry } from "@/lib/hooks/useLapTelemetry";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useEffect, useRef, useState, useCallback } from "react";
import { useTelemetrySettings } from "@/lib/hooks/useTelemetrySettings";
import { useCircuitInfo } from "@/lib/hooks/useCircuitInfo";
import { EChartsOption, getInstanceByDom } from "echarts";
import { useEcharts } from "@/lib/hooks/useEcharts";
import { defaultTelemetryChannelSettings } from "@/lib/utils";
import type { TelemetrySettings } from "@/lib/types";
import { Loader2, X, ZoomOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { lapAddedToast } from "@/lib/toasts";
import { parseSelectedLaps, toggleLap } from "@/lib/selectedLaps";
import { seriesKey } from "@/lib/seriesKey";
import { allocateColorSlots, lapColor } from "@/lib/colors";
import { useTelemetrySeries } from "@/lib/hooks/useTelemetrySeries";
import TelemetrySettingsPanel from "./TelemetrySettingsPanel";
import ColorSwatch from "../ui/ColorSwatch";
import { CHANNELS, GRID_GAP, GRID_HEIGHT } from "@/lib/constants";
import { CHART_STRUCTURE } from "@/lib/chartStructure";
import { buildTooltipFormatter } from "@/lib/buildTooltipFormatter";

function keysFromSelected(selected: Map<string, number[]>): string[] {
  return Array.from(selected.entries()).flatMap(([driver, lapNumbers]) =>
    lapNumbers.map((lap) => seriesKey(driver, lap)),
  );
}

function resolveChannelSettings(
  ts: TelemetrySettings,
  sIdx: number,
  total: number,
) {
  const chIdx = Math.floor(sIdx / Math.max(1, total / CHANNELS.length));
  const channel = CHANNELS[chIdx];
  return ts.useGlobalSettings
    ? ts.global
    : (ts.channels[channel as string] ?? defaultTelemetryChannelSettings);
}

export default function TelemetryViewer() {
  const telemetrySettings = useTelemetrySettings();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const year = searchParams.get("year") ?? "";
  const round = searchParams.get("round") ?? "";
  const session = searchParams.get("session") ?? "";
  const laps = searchParams.get("laps") ?? "";

  const chartRef = useEcharts();
  const hoveredSeriesRef = useRef<number | null>(null);
  const seriesRef = useRef<Array<{ name: string; id: string }>>([]);
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set());
  const [isZoomed, setIsZoomed] = useState(false);
  const [customColors, setCustomColors] = useState<Record<string, string>>({});
  const customColorsRef = useRef(customColors);
  const [colorSlots, setColorSlots] = useState<Record<string, number>>(() =>
    allocateColorSlots({}, keysFromSelected(parseSelectedLaps(laps))),
  );

  const toggleSeries = useCallback(
    (name: string) => {
      if (!chartRef.current) return;
      const chart = getInstanceByDom(chartRef.current);
      if (!chart) return;
      const isHidden = hiddenSeries.has(name);
      chart.dispatchAction({
        type: isHidden ? "legendSelect" : "legendUnSelect",
        name,
      });
      setHiddenSeries((prev) => {
        const next = new Set(prev);
        if (isHidden) next.delete(name);
        else next.add(name);
        return next;
      });
    },
    [hiddenSeries, chartRef],
  );

  const selectedLaps = useMemo(() => parseSelectedLaps(laps), [laps]);

  const removeLap = useCallback(
    (driver: string, lapNumber: number) => {
      toggleLap(selectedLaps, driver, lapNumber, {
        router,
        pathname,
        searchParams,
      });
    },
    [selectedLaps, router, pathname, searchParams],
  );

  // When the `laps` param changes, reconcile per-lap state against the new
  // selection: reassign stable color slots (so removing one lap doesn't recolor
  // the rest) and drop color/visibility overrides for laps that are no longer
  // selected so stale keys don't accumulate. Adjusting state during render
  // (rather than in an effect) is React's recommended pattern here.
  const [prevLaps, setPrevLaps] = useState(laps);
  if (laps !== prevLaps) {
    setPrevLaps(laps);
    const orderedKeys = keysFromSelected(selectedLaps);
    const validKeys = new Set(orderedKeys);
    setColorSlots((prev) => allocateColorSlots(prev, orderedKeys));
    setCustomColors((prev) => {
      const next = Object.fromEntries(
        Object.entries(prev).filter(([k]) => validKeys.has(k)),
      );
      return Object.keys(next).length === Object.keys(prev).length
        ? prev
        : next;
    });
    setHiddenSeries((prev) => {
      const next = new Set<string>();
      for (const k of prev) if (validKeys.has(k)) next.add(k);
      return next.size === prev.size ? prev : next;
    });
  }

  const { data: circuitData } = useCircuitInfo(year, round);
  const {data: telemetryData, isPending, failed, pending} = useLapTelemetry(year, round, session, selectedLaps);

  const shownToastsRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    const current = new Set(failed.map((f) => `${f.driver}-${f.lap}`));
    for (const key of shownToastsRef.current) {
      if (!current.has(key)) {
        toast.dismiss(`lap-fail-${key}`);
        shownToastsRef.current.delete(key);
      }
    }
    for (const f of failed) {
      const key = `${f.driver}-${f.lap}`;
      if (shownToastsRef.current.has(key)) continue;
      toast.error(`${f.driver} Lap ${f.lap} failed to load`, {
        id: `lap-fail-${key}`,
        action: {
          label: "Retry",
          onClick: () =>
            f.refetch().then((res) => {
              if (res.status === "success") lapAddedToast(f.driver, f.lap);
            }),
        },
        duration: Infinity,
        closeButton: true,
        className: "border-accent-red!"
      });
      shownToastsRef.current.add(key);
    }
  }, [failed]);

  useEffect(() => {
    customColorsRef.current = customColors;
  }, [customColors]);

  const {
    series,
    markLineSeries,
    legendItems,
    deltaBySeries,
    commonStart,
    commonEnd,
    refLapName,
    refTimes,
    error,
  } = useTelemetrySeries(telemetryData, circuitData, hiddenSeries, colorSlots);

  useEffect(() => {
    if (error) {
      toast.error(error, {
        id: "telemetry-range-error",
        className: "border-accent-red!",
      });
    } else {
      toast.dismiss("telemetry-range-error");
    }
  }, [error]);

  // seriesRef is read synchronously by the settings/colors merge effects
  // (whose deps don't include series), so it must stay in sync here.
  useEffect(() => {
    seriesRef.current = series;
  }, [series]);

  useEffect(() => {
    if (!chartRef.current) return;
    const chart = getInstanceByDom(chartRef.current);
    if (!chart) return;
    chart.on("mouseover", (params) => {
      if (params.componentType === "series") {
        hoveredSeriesRef.current = params.seriesIndex ?? null;
      }
    });
    chart.on("mouseout", () => {
      hoveredSeriesRef.current = null;
    });
    chart.on("globalout", () => {
      hoveredSeriesRef.current = null;
    });
    return () => {
      chart.off("mouseover");
      chart.off("mouseout");
      chart.off("globalout");
    };
  }, [chartRef]);

  useEffect(() => {
    if (!chartRef.current) return;
    const chart = getInstanceByDom(chartRef.current);
    if (!chart) return;
    chart.on("datazoom", (params) => {
      const p = params as {
        batch?: { start?: number; end?: number }[];
        start?: number;
        end?: number;
      };

      let start: number | undefined;
      let end: number | undefined;
      if (p.batch?.[0]) {
        start = p.batch[0].start;
        end = p.batch[0].end;
      } else {
        start = p.start;
        end = p.end;
      }

      if (start == null || end == null) return;
      setIsZoomed(start !== 0 || end !== 100);
    });
    return () => {
      chart.off("datazoom");
    };
  }, [chartRef]);

  const resetZoom = () => {
    if (!chartRef.current) return;
    const chart = getInstanceByDom(chartRef.current);
    if (!chart) return;
    chart.dispatchAction({ type: "dataZoom", start: 0, end: 100 });
    setIsZoomed(false);
  };

  useEffect(() => {
    if (!chartRef.current) return;
    const chart = getInstanceByDom(chartRef.current);
    if (!chart) return;

    const axisFormatter = buildTooltipFormatter({
      nLaps: series.length / CHANNELS.length,
      corners: circuitData?.corners ?? [],
      telemetryData,
      commonStart,
      commonEnd,
      deltaBySeries,
      refLapName,
      refTimes,
      hoveredSeriesRef,
    });

    chart.setOption<EChartsOption>(
      {
        ...CHART_STRUCTURE,

        tooltip: {
          trigger: "axis" as const,
          backgroundColor: "oklch(17.76% 0.000 0)",
          borderColor: "oklch(28.50% 0.000 0)",
          axisPointer: { type: "line" as const },
          formatter: axisFormatter,
        },

        series: [
          ...series.map((s, sIdx) => {
            const ch = resolveChannelSettings(telemetrySettings, sIdx, series.length);
            return {
              showSymbol: ch.showSymbol,
              symbol: ch.symbol,
              symbolSize: ch.symbolSize,
              smooth: ch.smooth,
              lineStyle: { width: ch.lineWidth },
              ...s,
              color: customColorsRef.current[s.name] ?? s.color,
            };
          }),
          ...markLineSeries,
        ],
      },
      { replaceMerge: ["series"] },
    );

    for (const name of hiddenSeries) {
      chart.dispatchAction({ type: "legendUnSelect", name });
    }
  }, [
    series,
    chartRef,
    circuitData,
    telemetryData,
    commonStart,
    commonEnd,
    deltaBySeries,
    refLapName,
    refTimes,
  ]);

  // Settings-only update — merge mode so zoom and chart structure are preserved
  useEffect(() => {
    if (!chartRef.current) return;
    const chart = getInstanceByDom(chartRef.current);
    if (!chart) return;
    const currentSeries = seriesRef.current;
    if (!currentSeries.length) return;
    chart.setOption({
      series: [
        ...currentSeries.map((s, sIdx) => {
          const ch = resolveChannelSettings(
            telemetrySettings,
            sIdx,
            currentSeries.length,
          );
          return {
            id: s.id,
            smooth: ch.smooth,
            showSymbol: ch.showSymbol,
            symbol: ch.symbol,
            symbolSize: ch.symbolSize,
            lineStyle: { width: ch.lineWidth },
          };
        }),
        ...CHANNELS.map((_, i) => ({ id: `__markline_${i}` })),
      ],
    });
  }, [telemetrySettings, chartRef]);

  // Color-only update — merge mode so zoom and chart structure are preserved
  useEffect(() => {
    if (!chartRef.current) return;
    const chart = getInstanceByDom(chartRef.current);
    if (!chart) return;
    const current = seriesRef.current;
    if (!current.length) return;
    chart.setOption({
      series: [
        ...current.map((s) =>
          customColors[s.name]
            ? { id: s.id, color: customColors[s.name] }
            : { id: s.id },
        ),
        ...CHANNELS.map((_, i) => ({ id: `__markline_${i}` })),
      ],
    });
  }, [customColors, chartRef]);

  // Laps still fetching that aren't yet drawn — surfaced in the legend with a
  // spinner so the user sees a pending lap appear immediately on selection.
  const loadedKeys = useMemo(
    () => new Set(legendItems.map((i) => i.key)),
    [legendItems],
  );
  const pendingItems = useMemo(
    () =>
      pending
        .map(({ driver, lap }) => ({ key: seriesKey(driver, lap), driver, lap }))
        .filter((p) => !loadedKeys.has(p.key)),
    [pending, loadedKeys],
  );

  const totalHeight = CHANNELS.length * (GRID_HEIGHT + GRID_GAP) + GRID_GAP;

  const chartAriaLabel =
    legendItems.length === 0
      ? "Telemetry chart, no laps selected"
      : `Telemetry comparison chart for ${legendItems
          .map((i) => `${i.driver} lap ${i.lap}`)
          .join(", ")}. Channels ${CHANNELS.join(
          ", ",
        )} plotted against lap distance.`;

  return (
    <div className="bg-surface-base">
      <div className="flex flex-col gap-4">
        <div className="border border-surface-border bg-surface-base flex flex-col items-start py-8 px-4 rounded-xs">
          <div className="w-full flex flex-col min-w-0 px-4 py-4 gap-4 overflow-hidden">
            <div className="relative flex items-center justify-center py-0 pl-2 pr-5 gap-2">
              <div className="flex flex-wrap gap-x-4 gap-y-2 w-full justify-center">
                {legendItems.map((item) => {
                  const hidden = hiddenSeries.has(item.key);
                  const effectiveColor = customColors[item.key] ?? item.color;
                  return (
                    <div
                      key={item.key}
                      className="group flex items-center gap-2 rounded-full border border-surface-border bg-surface-card py-1 pl-2 pr-1 transition-opacity"
                      style={{ opacity: hidden ? 0.3 : 1 }}
                    >
                      <ColorSwatch
                        color={effectiveColor}
                        label={`Change color for ${item.driver} Lap ${item.lap}`}
                        onCommit={(c) =>
                          setCustomColors((prev) => ({
                            ...prev,
                            [item.key]: c,
                          }))
                        }
                      />
                      <button
                        type="button"
                        aria-pressed={!hidden}
                        aria-label={`${hidden ? "Show" : "Hide"} ${item.driver} Lap ${item.lap} in chart`}
                        onClick={() => toggleSeries(item.key)}
                        className={`text-xs text-text-muted cursor-pointer rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50 ${
                          hidden ? "line-through" : ""
                        }`}
                      >
                        {item.driver} Lap {item.lap}
                      </button>
                      <button
                        type="button"
                        aria-label={`Remove ${item.driver} Lap ${item.lap}`}
                        title={`Remove ${item.driver} Lap ${item.lap}`}
                        onClick={() => removeLap(item.driver, item.lap)}
                        className="flex size-5 items-center justify-center rounded-full text-text-muted cursor-pointer outline-none transition-colors hover:bg-accent-red/15 hover:text-accent-red focus-visible:ring-2 focus-visible:ring-accent-red/50"
                      >
                        <X size={12} aria-hidden="true" />
                      </button>
                    </div>
                  );
                })}
                {pendingItems.map((item) => {
                  const color =
                    customColors[item.key] ??
                    lapColor(colorSlots[item.key] ?? 0);
                  return (
                    <div
                      key={item.key}
                      role="status"
                      aria-live="polite"
                      className="flex items-center gap-2 rounded-full border border-surface-border bg-surface-card py-1 pl-2 pr-3"
                      style={{ opacity: 0.6 }}
                    >
                      <span
                        className="size-3 rounded-full"
                        style={{ backgroundColor: color }}
                        aria-hidden="true"
                      />
                      <span className="text-xs text-text-muted">
                        {item.driver} Lap {item.lap}
                      </span>
                      <Loader2
                        className="animate-spin text-text-muted"
                        size={12}
                        aria-label={`Loading ${item.driver} Lap ${item.lap}`}
                      />
                    </div>
                  );
                })}
              </div>
              <TelemetrySettingsPanel />
            </div>
            <div
              className="relative w-full border border-surface-border bg-surface-card"
              style={{ height: totalHeight }}
            >
              <div
                ref={chartRef}
                role="img"
                aria-label={chartAriaLabel}
                className="w-full h-full"
              />
              {isPending && telemetryData.length === 0 && (
                <div
                  role="status"
                  aria-live="polite"
                  className="absolute inset-0 flex items-center justify-center gap-2 text-sm text-text-muted"
                >
                  <Loader2 className="animate-spin" size={16} aria-hidden="true" />
                  Loading telemetry…
                </div>
              )}
            </div>
            <div className="flex justify-end pl-2 pr-5 min-h-9 -translate-y-2">
              {isZoomed && (
                <Button
                  size="sm"
                  variant="outline"
                  className="text-xs cursor-pointer text-accent-green border-surface-border bg-surface-card py-4 rounded-none hover:bg-surface-card-hover hover:text-accent-green"
                  onClick={resetZoom}
                >
                  <ZoomOut size={8} aria-hidden="true" /> Reset Zoom
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
