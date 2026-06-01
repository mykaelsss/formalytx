import { toast } from "sonner";

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
