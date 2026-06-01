import { useSyncExternalStore, useCallback } from "react";
import type { ChartSettings } from "../types";
import { defaultChartSettings } from "../utils";

const GLOBAL_KEY = "chart_settings_global";
const scopedKey = (id: string) => `chart_settings_scoped_${id}`;
const modeKey = (id: string) => `chart_settings_mode_${id}`;

// --- global layer ---
let globalSnapshot: ChartSettings | null = null;

function readGlobal(): ChartSettings {
  if (globalSnapshot) return globalSnapshot;
  let next: ChartSettings;
  try {
    const stored = localStorage.getItem(GLOBAL_KEY);
    next = stored
      ? { ...defaultChartSettings, ...JSON.parse(stored) }
      : defaultChartSettings;
  } catch {
    next = defaultChartSettings;
  }
  globalSnapshot = next;
  return next;
}

// --- scoped layer (per chart id) ---
const scopedCache = new Map<string, ChartSettings>();

function readScoped(id: string): ChartSettings {
  const cached = scopedCache.get(id);
  if (cached !== undefined) return cached;
  let next: ChartSettings;
  try {
    const stored = localStorage.getItem(scopedKey(id));
    next = stored
      ? { ...defaultChartSettings, ...JSON.parse(stored) }
      : readGlobal(); // seed a new scoped chart from current global
  } catch {
    next = defaultChartSettings;
  }
  scopedCache.set(id, next);
  return next;
}

// --- mode (per chart id) ---
const modeCache = new Map<string, "shared" | "scoped">();

function readMode(id: string): "shared" | "scoped" {
  const cached = modeCache.get(id);
  if (cached !== undefined) return cached;
  let mode: "shared" | "scoped";
  try {
    mode = (localStorage.getItem(modeKey(id)) as "shared" | "scoped") ?? "shared";
  } catch {
    mode = "shared";
  }
  modeCache.set(id, mode);
  return mode;
}

// --- listeners, per chart id ---
const listenersById = new Map<string, Set<() => void>>();
let totalListeners = 0;

function emitChart(id: string) {
  const set = listenersById.get(id);
  if (set) for (const l of set) l();
}

function emitSharedCharts() {
  // every chart currently in shared mode needs to re-read
  for (const [id, set] of listenersById) {
    if (readMode(id) === "shared") for (const l of set) l();
  }
}

// --- effective snapshot a component reads ---
function readSnapshot(id: string): ChartSettings {
  return readMode(id) === "shared" ? readGlobal() : readScoped(id);
}

// --- writes ---
export function updateChartSettings(id: string, settings: ChartSettings) {
  if (readMode(id) === "shared") {
    // editing a shared chart edits global → all shared charts update
    if (globalSnapshot === settings) return;
    globalSnapshot = settings;
    try { localStorage.setItem(GLOBAL_KEY, JSON.stringify(settings)); }
    catch (err) { console.error(err); }
    emitSharedCharts();
  } else {
    if (scopedCache.get(id) === settings) return;
    scopedCache.set(id, settings);
    try { localStorage.setItem(scopedKey(id), JSON.stringify(settings)); }
    catch (err) { console.error(err); }
    emitChart(id);
  }
}

export function setChartMode(id: string, mode: "shared" | "scoped") {
  if (readMode(id) === mode) return;
  modeCache.set(id, mode);
  try { localStorage.setItem(modeKey(id), mode); }
  catch (err) { console.error(err); }

  if (mode === "scoped") {
    // entering scoped: snapshot current global as the chart's starting point
    scopedCache.set(id, readGlobal());
    try { localStorage.setItem(scopedKey(id), JSON.stringify(readGlobal())); }
    catch (err) { console.error(err); }
  }
  emitChart(id); // this chart's effective settings just changed source
}

// --- cross-tab ---
function handleStorage(e: StorageEvent) {
  if (!e.key) return;
  if (e.key === GLOBAL_KEY) {
    globalSnapshot = null;
    emitSharedCharts();
  } else if (e.key.startsWith("chart_settings_scoped_")) {
    const id = e.key.replace("chart_settings_scoped_", "");
    scopedCache.delete(id);
    emitChart(id);
  } else if (e.key.startsWith("chart_settings_mode_")) {
    const id = e.key.replace("chart_settings_mode_", "");
    modeCache.delete(id);
    emitChart(id);
  }
}

function subscribe(id: string, cb: () => void) {
  if (totalListeners === 0 && typeof window !== "undefined") {
    window.addEventListener("storage", handleStorage);
  }
  let set = listenersById.get(id);
  if (!set) { set = new Set(); listenersById.set(id, set); }
  set.add(cb);
  totalListeners++;

  return () => {
    set.delete(cb);
    totalListeners--;
    if (set.size === 0) listenersById.delete(id);
    if (totalListeners === 0 && typeof window !== "undefined") {
      window.removeEventListener("storage", handleStorage);
    }
  };
}

const getServerSnapshot = () => defaultChartSettings;
const getServerMode = () => "shared" as const;


export function useChartSettings(id: string) {
  const subscribeForId = useCallback((cb: () => void) => subscribe(id, cb), [id]);
  const getSnapshot = useCallback(() => readSnapshot(id), [id]);
  const getMode = useCallback(() => readMode(id), [id]);
  const settings = useSyncExternalStore(subscribeForId, getSnapshot, getServerSnapshot);
  const mode = useSyncExternalStore(subscribeForId, getMode, getServerMode);

  return {
    settings,
    mode,
    setSettings: (s: ChartSettings) => updateChartSettings(id, s),
    setMode: (m: "shared" | "scoped") => setChartMode(id, m),
  };
}