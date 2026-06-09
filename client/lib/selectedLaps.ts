import type { ReadonlyURLSearchParams } from "next/navigation";
import {
  consumeLapAwaitingReview,
  lapAddedToast,
  markLapAwaitingReview,
} from "./toasts";
import { seriesKey } from "./seriesKey";

export function parseSelectedLaps(laps: string): Map<string, number[]> {
  return laps.split("|").reduce((map, entry) => {
    const [driver, lapsStr] = entry.split(":");
    if (!driver || !lapsStr) return map;
    const lapNumbers = lapsStr
      .split(",")
      .map(Number)
      .filter((n) => Number.isInteger(n) && n > 0);
    if (lapNumbers.length) map.set(driver, lapNumbers);
    return map;
  }, new Map<string, number[]>());
}

type NavCtx = {
  router: { push: (url: string, options?: { scroll?: boolean }) => void };
  pathname: string;
  searchParams: ReadonlyURLSearchParams;
};

export function toggleLap(
  selectedLaps: Map<string, number[]>,
  driver: string,
  lapNumber: number,
  { router, pathname, searchParams }: NavCtx,
) {
  const currentLaps = selectedLaps.get(driver) ?? [];
  const idx = currentLaps.indexOf(lapNumber);
  const newLaps =
    idx === -1
      ? [...currentLaps, lapNumber]
      : currentLaps.filter((_, i) => i !== idx);
  const updated = new Map(selectedLaps);
  if (newLaps.length) updated.set(driver, newLaps);
  else updated.delete(driver);
  const lapsStr = Array.from(updated.entries())
    .map(([d, ls]) => `${d}:${ls.join(",")}`)
    .join("|");

  const params = new URLSearchParams(searchParams.toString());
  params.set("laps", lapsStr);
  router.push(pathname + "?" + params.toString(), { scroll: false });

  if (idx === -1) {
    markLapAwaitingReview(seriesKey(driver, lapNumber));
    const viewParams = new URLSearchParams(searchParams.toString());
    viewParams.set("laps", lapsStr);
    viewParams.set("tab", "telemetry");
    const viewUrl = pathname + "?" + viewParams.toString();
    lapAddedToast(driver, lapNumber, () => router.push(viewUrl));
  } else {
    consumeLapAwaitingReview(seriesKey(driver, lapNumber));
  }
}
