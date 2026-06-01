import { useSyncExternalStore } from "react";
import type { TelemetrySettings } from "../types";
import { defaultTelemetrySettings } from "../utils";

const STORAGE_KEY = "telemetry_grid_settings";
let snapshot: TelemetrySettings | null = null;
const listeners = new Set<() => void>();

function readSnapshot(): TelemetrySettings {
  if (snapshot) return snapshot;
  let next: TelemetrySettings;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    next = stored
      ? { ...defaultTelemetrySettings, ...JSON.parse(stored) }
      : defaultTelemetrySettings;
  } catch {
    next = defaultTelemetrySettings;
  }
  snapshot = next;
  return next;
}

export function setTelemetrySettings(settings: TelemetrySettings) {
  if (snapshot === settings) return;
  snapshot = settings;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // Storage unavailable; keep in-memory state and continue.
  }
  for (const l of listeners) l();
}

const subscribe = (cb: () => void) => {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
};

const getServerSnapshot = () => defaultTelemetrySettings;

export function useTelemetrySettings(): TelemetrySettings {
  return useSyncExternalStore(subscribe, readSnapshot, getServerSnapshot);
}