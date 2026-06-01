import type { EChartsOption } from "echarts";
import {
  CHANNELS,
  GRID_GAP,
  GRID_HEIGHT,
  LEFT_MARGIN,
  RIGHT_MARGIN,
} from "./constants";

const yAxisDefaults = {
  axisLine: { show: false },
  axisTick: { show: false },
  splitLine: {
    show: true,
    lineStyle: { color: "#333", type: "dashed" as const },
  },
  min: (v: { min: number; max: number }) => Math.floor(v.min),
  max: (v: { min: number; max: number }) => Math.ceil(v.max),
  minInterval: 1,
};

const xAxisDefaults = {
  axisLine: { show: false },
  axisTick: { show: false },
  splitLine: { show: false },
  axisLabel: { show: false },
  min: (v: { min: number; max: number }) => Math.floor(v.min),
  max: (v: { min: number; max: number }) => Math.ceil(v.max),
};

// Invariant chart skeleton — depends only on CHANNELS and layout constants,
// so it's built once rather than rebuilt on every chart update.
export const CHART_STRUCTURE: Pick<
  EChartsOption,
  "grid" | "xAxis" | "yAxis" | "axisPointer" | "dataZoom" | "legend"
> = {
  grid: CHANNELS.map((_, i) => ({
    top: i * (GRID_HEIGHT + GRID_GAP) + GRID_GAP,
    height: GRID_HEIGHT,
    left: LEFT_MARGIN,
    right: RIGHT_MARGIN,
    backgroundColor: "oklch(14.48% 0.000 0)",
    show: true,
  })),

  xAxis: CHANNELS.map((_, i) => ({
    type: "value" as const,
    gridIndex: i,
    ...xAxisDefaults,
  })),

  yAxis: CHANNELS.map((channel, i) => {
    const base = {
      type: "value" as const,
      gridIndex: i,
      name: channel === "delta" ? "Delta (s)" : channel,
      nameLocation: "middle" as const,
      nameGap: 45,
      nameTextStyle: { color: "#888", fontSize: 11 },
      ...yAxisDefaults,
    };
    if (channel === "gear") return { ...base, min: 1 };
    if (channel === "brake") {
      return {
        ...base,
        min: 0,
        max: 1,
        minInterval: 1,
        axisLabel: {
          formatter: (v: number) => (v === 1 ? "ON" : v === 0 ? "OFF" : ""),
        },
      };
    }
    if (channel === "delta") {
      return {
        ...base,
        min: (v: { min: number; max: number }) => {
          const bound = Math.max(Math.abs(v.min), Math.abs(v.max), 0.5);
          return -Math.ceil(bound * 10) / 10;
        },
        max: (v: { min: number; max: number }) => {
          const bound = Math.max(Math.abs(v.min), Math.abs(v.max), 0.5);
          return Math.ceil(bound * 10) / 10;
        },
      };
    }
    return base;
  }),

  axisPointer: {
    link: [{ xAxisIndex: "all" }],
    lineStyle: { color: "#555" },
  },

  dataZoom: [
    {
      type: "inside" as const,
      xAxisIndex: CHANNELS.map((_, i) => i),
      minValueSpan: 100,
    },
  ],

  legend: { show: false },
};
