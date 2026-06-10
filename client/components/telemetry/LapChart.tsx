"use client";

import { format, type LineSeriesOption } from "echarts";
import type { TopLevelFormatterParams } from "echarts/types/dist/shared";
import type { Team } from "@/lib/types";
import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Chart from "../chart/Chart";
import { useChartSettings } from "@/lib/hooks/useChartSettings";
import { CHART_STORAGE_KEYS } from "@/lib/constants";
import { toggleLap, parseSelectedLaps } from "@/lib/selectedLaps";
import { useSessionLaps } from "@/lib/hooks/useSessionLaps";
import { useQueryClient } from "@tanstack/react-query";

interface LapChartProps {
  teams: Team[];
}

function lapTimeToSeconds(lapTime: string | null): number | null {
  if (!lapTime) return null;
  const [min, sec] = lapTime.split(":");
  if (!min || !sec) return null;
  return parseInt(min) * 60 + parseFloat(sec);
}

function secondsToLapTime(seconds: number, precision = 2): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0");
  const ms = Math.round((seconds % 1) * Math.pow(10, precision))
    .toString()
    .padStart(precision, "0");
  return precision > 0 ? `${m}:${s}.${ms}` : `${m}:${s}`;
}

export default function LapChart({ teams }: LapChartProps) {
  const settings = useChartSettings(CHART_STORAGE_KEYS.lapChart).settings;
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

  const driverMap = useMemo(
    () =>
      new Map(teams.flatMap((t) => t.drivers).map((d) => [d.abbreviation, d])),
    [teams],
  );

  const { driverLaps, isLoading: isLoadingLaps } = useSessionLaps(year, round, session, selectedDrivers)
  
  const visibleLaps = useMemo(
    () => driverLaps.filter((d) => selectedDrivers.includes(d.abbreviation)),
    [driverLaps, selectedDrivers],
  );

  const secondDrivers = useMemo(() => {
    const seen = new Set<string>();
    const second = new Set<string>();
    for (const d of visibleLaps) {
      const driver = driverMap.get(d.abbreviation);
      if (!driver) continue;
      if (seen.has(driver.team_name)) {
        second.add(d.abbreviation);
      } else {
        seen.add(driver.team_name);
      }
    }
    return second;
  }, [visibleLaps, driverMap]);

  const chartData = useMemo(() => {
    if (visibleLaps.length === 0) return [];

    const allTimes = visibleLaps.flatMap((d) =>
      d.laps
        .map((l) => lapTimeToSeconds(l.lap_time))
        .filter((t): t is number => t !== null),
    );

    const fastest = Math.min(...allTimes);
    const cutoff = fastest * (1 + settings.outlierThreshold / 100);

    const lapLengths = visibleLaps.map((d) => d.laps.length);
    const maxLaps = Math.max(...lapLengths);

    const allPoints = Array.from({ length: maxLaps }, (_, i) => {
      const point: Record<string, number | null> = { lap: i + 1 };
      for (const d of visibleLaps) {
        const lap = d.laps[i];
        const secs = lap ? lapTimeToSeconds(lap.lap_time) : null;
        point[d.abbreviation] = secs !== null && secs <= cutoff ? secs : null;
      }
      return point;
    });

    return allPoints;
  }, [visibleLaps, settings.outlierThreshold]);

  const tooltipFormatter = useCallback((params: TopLevelFormatterParams) => {
    const items = Array.isArray(params) ? params : [params];
    const rows = items
      .filter((p) => p.value != null)
      .map((p) => {
        const isSecond = secondDrivers.has(p.seriesName ?? "");
        const lineStyle = isSecond
          ? settings.secondDriverLineStyle
          : settings.firstDriverLineStyle;
        const marker = `
                    <span 
                    class="inline-block w-5 mr-2 border-t-2" 
                    style="border-color:${format.encodeHTML(p.color as string)};border-style:${format.encodeHTML(lineStyle)};">
                    </span>
                  `;
        return `
                <div class="flex justify-between gap-2">
                  <div class="flex items-center">
                    ${marker}
                    <span
                    class="leading-none">${format.encodeHTML(p.seriesName ?? "")}
                    </span>
                  </div>
                  <span class="font-mono">
                  ${format.encodeHTML(secondsToLapTime((p.value as [number, number])[1], 3))}
                  </span>
                </div>`;
      })
      .join("");

    const lap = (items[0]?.value as [number, number])?.[0];

    return `
              <div class="text-xs text-white">
                <span>Lap ${format.encodeHTML(String(lap))}</span>
                ${rows}
              </div>
            `;
  }, [settings.secondDriverLineStyle, settings.firstDriverLineStyle, secondDrivers]);

  const legendItems = useMemo(() => visibleLaps
    .filter((d) => driverMap.has(d.abbreviation))
    .map((d) => ({
      key: d.abbreviation,
      driver: driverMap.get(d.abbreviation)!,
      isSecond: secondDrivers.has(d.abbreviation),
    })), [driverMap, visibleLaps, secondDrivers]);

  const series = useMemo<LineSeriesOption[]>(() => {
    return visibleLaps.flatMap((d) => {
      const driver = driverMap.get(d.abbreviation);
      if (!driver) return [];
      const isSecondDriver = secondDrivers.has(d.abbreviation);
      return {
        id: d.abbreviation,
        name: d.abbreviation,
        color: `#${driver.team_color}`,
        lineStyle: isSecondDriver
          ? {
              type: settings.secondDriverLineStyle,
              dashOffset: 0,
              width: settings.lineWidth,
            }
          : {
              type: settings.firstDriverLineStyle,
              dashOffset: 0,
              width: settings.lineWidth,
            },
        data: chartData
          .filter((p) => p[d.abbreviation] != null)
          .map((p) => [p['lap'], p[d.abbreviation]]),
      };
    });
  }, [
    chartData,
    visibleLaps,
    driverMap,
    secondDrivers,
    settings.secondDriverLineStyle,
    settings.firstDriverLineStyle,
    settings.lineWidth,
  ]);

  const selectedLaps = useMemo(() => parseSelectedLaps(laps), [laps]);

  const handleSeriesClick = useCallback(({ seriesName, value }: { seriesName: string; value: [number, number] }) => {
    toggleLap(
      selectedLaps,
      { year, round, session, driver: seriesName, lap: value[0] },
      { router, pathname, searchParams, queryClient },
    );
  }, [selectedLaps, year, round, session, pathname, router, searchParams, queryClient]);

  return (
    <Chart
      title="Lap times · Time vs lap"
      emptyHint="Select drivers from the panel to plot their lap times."
      tooltipFormatter={tooltipFormatter}
      yAxisFormatter={(val: number) => secondsToLapTime(val, 0)}
      storageKey={CHART_STORAGE_KEYS.lapChart}
      series={series}
      legendItems={legendItems}
      onSeriesClick={handleSeriesClick}
      renderLegendItem={(item) => (
        <>
          <span
            className="w-6 border-t-2"
            style={{
              borderColor: `#${item.driver.team_color}`,
              borderStyle: item.isSecond
                ? settings.secondDriverLineStyle
                : settings.firstDriverLineStyle,
            }}
          />
          <span className="font-mono text-[10px] tracking-wider text-text-secondary">
            {item.driver.abbreviation}
          </span>
        </>
      )}
      isLoading={isLoadingLaps}
    />
  );
}
