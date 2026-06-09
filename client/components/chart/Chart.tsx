"use client";

import { getInstanceByDom, type EChartsOption, type LineSeriesOption } from "echarts";
import type { TopLevelFormatterParams } from "echarts/types/dist/shared";
import type { ChartSettings } from "@/lib/types";
import { ZoomOut } from "lucide-react";
import { useState, useEffect, useCallback } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import ChartSettingsPanel from "./ChartSettingsPanel";
import { useChartSettings } from "@/lib/hooks/useChartSettings";
import { useEcharts } from "@/lib/hooks/useEcharts";
import { useToggleSeries } from "@/lib/hooks/useToggleSeries";

type LegendItem = {
  key: string;
  label?: string;
};

interface ChartProps<T extends LegendItem> {
  series: LineSeriesOption[];
  storageKey?: string;
  tooltipFormatter?: (params: TopLevelFormatterParams) => string;
  yAxisFormatter?: (val: number) => string;
  legendItems?: T[];
  renderLegendItem: (item: T, state: { hidden: boolean }) => React.ReactNode;
  isLoading?: boolean;
  onSeriesClick?: (params: { seriesName: string; value: [number, number] }) => void;
}

export default function Chart<T extends LegendItem>({
  series,
  storageKey = "lap_chart_settings",
  tooltipFormatter,
  yAxisFormatter,
  legendItems,
  renderLegendItem,
  isLoading = false,
  onSeriesClick,
}: ChartProps<T>) {
  const chartRef = useEcharts();

  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set());
  const [isZoomed, setIsZoomed] = useState(false);
  const {settings, setSettings} = useChartSettings(storageKey);

  const updateSettings = useCallback(
    (next: ChartSettings | ((prev: ChartSettings) => ChartSettings)) => {
      const value = typeof next === "function" ? next(settings) : next;
      setSettings(value);
    },
    [settings, setSettings],
  );

  useEffect(() => {
    if (!chartRef.current) return;
    const chart = getInstanceByDom(chartRef.current);
    if (!chart) return;

    const seriesDefaults = {
      type: "line" as const,
      symbol: settings.symbol,
      showSymbol: settings.showSymbol,
      smooth: settings.smooth,
      symbolSize: settings.symbolSize,
      itemStyle: {
        borderColor: "oklch(74.90% 0.000 0)",
        borderWidth: 1,
      },
      emphasis: {
        itemStyle: { color: "inherit" },
        areaStyle: { color: "inherit" },
      },
    };

    const toolTipDefaults = {
      trigger: "axis" as const,
      backgroundColor: "oklch(17.76% 0.000 0)",
      borderColor: "oklch(28.50% 0.000 0)",
      enterable: true,
      axisPointer: {
        type: "line" as const,
        z: 0,
        lineStyle: { color: "#555", opacity: 0.8 },
      },
    };

    chart.setOption<EChartsOption>(
      {
        grid: {
          backgroundColor: "oklch(14.48% 0.000 0)",
          borderColor: "oklch(28.50% 0.000 0)",
          borderWidth: 2,
          top: 2,
          right: 2,
          left: 2,
          bottom: 2,
          show: true,
          outerBounds: {
            right: 15,
            left: 15,
            bottom: 15,
          },
        },
        xAxis: {
          type: "value",
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: {
            show: true,
            lineStyle: { color: "#333", type: "dashed" },
            showMinLine: false,
            showMaxLine: false,
          },
          axisLabel: {
            alignMinLabel: "left",
            alignMaxLabel: "right",
          },
          min: (value: { min: number; max: number }) => Math.floor(value.min),
          max: (value: { min: number; max: number }) => Math.ceil(value.max),
        },
        yAxis: {
          type: "value",
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: {
            show: true,
            lineStyle: { color: "#333", type: "dashed" },
            showMinLine: false,
            showMaxLine: false,
          },
          minInterval: 1,
          axisLabel: {
            margin: 20,
            verticalAlignMinLabel: "bottom",
            verticalAlignMaxLabel: "top",
            formatter: yAxisFormatter,
          },
          min: (value: { min: number; max: number }) => Math.floor(value.min),
          max: (value: { min: number; max: number }) => Math.ceil(value.max),
        },
        tooltip: {
          formatter: tooltipFormatter,
          ...toolTipDefaults,
        },
        dataZoom: {
          type: "inside",
          minValueSpan: 5,
        },
        legend: { show: false },
        series: series.map((s) => ({
          ...seriesDefaults,
          ...s,
        })),
      },
      { replaceMerge: ["series"] },
    );
  }, [
    series,
    tooltipFormatter,
    yAxisFormatter,
    settings.smooth,
    settings.showSymbol,
    settings.symbol,
    settings.symbolSize,
    settings.lineWidth,
    settings.firstDriverLineStyle,
    settings.secondDriverLineStyle,
    chartRef
  ]);

  useEffect(() => {
    if (!chartRef.current || !onSeriesClick) return;
    const chart = getInstanceByDom(chartRef.current);
    if (!chart) return;
    chart.on("click", (params) => {
      if (params.componentType === "series") {
        onSeriesClick({ seriesName: params.seriesName ?? "", value: params.value as [number, number] });
      }
    });
    return () => { chart.off("click"); };
  }, [onSeriesClick, chartRef]);

  useEffect(() => {
    if (!chartRef.current) return;
    const chart = getInstanceByDom(chartRef.current);
    if (!chart) return;

    chart.on("mouseover", (params) => {
      if (params.componentType !== "series") return;
      const option = chart.getOption() as { series: { data: unknown[] }[] };
      chart.setOption({
        series: option.series.map((s, sIdx) => ({
          data: s.data.map((d: unknown, dIdx: number) => {
            const val = Array.isArray(d) ? d : (d as { value: unknown }).value;
            const isTarget = sIdx === params.seriesIndex && dIdx === params.dataIndex;
            return { value: val, symbolSize: isTarget ? settings.symbolSize * 1.5 : settings.symbolSize, z: isTarget ? 100 : 1 };
          }),
        })),
      });
    });

    chart.on("mouseout", () => {
      const option = chart.getOption() as { series: { data: unknown[] }[] };
      chart.setOption({
        series: option.series.map((s) => ({
          data: s.data.map((d: unknown) => {
            const val = Array.isArray(d) ? d : (d as { value: unknown }).value;
            return { value: val, symbolSize: settings.symbolSize, z: 1 };
          }),
        })),
      });
    });

    return () => {
      chart.off("mouseover");
      chart.off("mouseout");
    };
  }, [settings.symbolSize, chartRef]);

  useEffect(() => {
    if (!chartRef.current) return;
    const chart = getInstanceByDom(chartRef.current);
    if (!chart) return;
    chart.on("datazoom", () => {
      const option = chart.getOption() as {
        dataZoom?: { start?: number; end?: number }[];
      };
      const zoom = option.dataZoom?.[0];
      setIsZoomed(zoom?.start !== 0 || zoom?.end !== 100);
    });
    return () => {
      chart.off("datazoom");
    };
  }, [chartRef]);

  const resetZoom = () => {
    const chart = getInstanceByDom(chartRef.current!);
    if (!chart) return;
    chart.dispatchAction({ type: "dataZoom", start: 0, end: 100 });
    setIsZoomed(false);
  };

  const toggleSeries = useToggleSeries(hiddenSeries, setHiddenSeries, chartRef)

  return (
    <div className="w-full h-120 flex flex-col border border-surface-border bg-surface-card">
      <div className="relative flex items-center justify-center py-4 pl-2 pr-5 gap-2">
        <div className="flex flex-wrap gap-x-4 gap-y-2 w-full justify-center">
          {legendItems?.map((item) => {
            const hidden = hiddenSeries.has(item.key);
            return (
              <button
                type="button"
                key={item.key}
                onClick={() => toggleSeries(item.key)}
                className="flex items-center gap-2 cursor-pointer"
                style={{ opacity: hidden ? 0.3 : 1 }}
              >
                {renderLegendItem(item, { hidden })}
              </button>
            );
          })}
        </div>
        <ChartSettingsPanel settings={settings} setSettings={updateSettings} />
      </div>
      <div className="relative w-full flex-1">
        <div ref={chartRef} className="w-full h-full" />
        {isLoading && series.length === 0 && (
          <Skeleton className="absolute inset-0 rounded-none bg-surface-base" />
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
            <ZoomOut size={8} /> Reset Zoom
          </Button>
        )}
      </div>
    </div>
  );
}
