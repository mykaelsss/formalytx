import { toast } from "sonner";

// Laps the user just added that are still fetching telemetry. Once their data
// renders, TelemetryViewer fires lapReadyToast and clears the mark.
const awaitingReview = new Set<string>();

export function markLapAwaitingReview(key: string) {
  awaitingReview.add(key);
}

export function consumeLapAwaitingReview(key: string): boolean {
  return awaitingReview.delete(key);
}

export function lapAddedToast(driver: string, lap: number, onView?: () => void) {
  toast.success(`${driver} Lap ${lap} added`, {
    id: `lap-added-${driver}-${lap}`,
    className: "border-accent-green!",
    action: onView
      ? {
          label: "View",
          onClick: onView,
        }
      : undefined,
  });
}

export function lapReadyToast(driver: string, lap: number, onView?: () => void) {
  toast.success(`${driver} Lap ${lap} ready for review`, {
    id: `lap-ready-${driver}-${lap}`,
    className: "border-accent-green!",
    action: onView
      ? {
          label: "View",
          onClick: onView,
        }
      : undefined,
  });
}
