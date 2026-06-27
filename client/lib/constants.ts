import { Options } from "nuqs";

export const CHART_STORAGE_KEYS = {
  lapChart: "lap_chart_settings",
} as const;

const TELEMETRY_CHANNELS = [
  "speed",
  "throttle",
  "brake",
  "rpm",
  "gear",
] as const;
export type TelemetryChannel = (typeof TELEMETRY_CHANNELS)[number];

export const CHANNELS = [...TELEMETRY_CHANNELS, "delta"] as const;
export type Channel = (typeof CHANNELS)[number];

export const GRID_HEIGHT = 120;
export const GRID_GAP = 48;
export const LEFT_MARGIN = 60;
export const RIGHT_MARGIN = 20;
export const SAMPLE_COUNT = 1000;

export const DEFAULT_NUQS_OPTIONS = {
  defaultValue: "",
  scroll: false,
} satisfies Options & { defaultValue: string };