import { Suspense } from "react";
import type { Metadata } from "next";
import TelemetryTabs from "@/components/telemetry/TelemetryTabs";

export const metadata: Metadata = {
  title: "Telemetry",
  description: "Compare lap times and car telemetry across drivers and sessions.",
};

export default async function TelemetryPage({
  searchParams
}: {
  searchParams: Promise<{ tab?: string; year?: string; event?: string; session?: string }>
}) {

  const params = await searchParams;
  const tab = params.tab ?? "session";

  return (
    <main>
      <Suspense fallback={<TelemetryTabsSkeleton />}>
        <TelemetryTabs activeTab={tab} />
      </Suspense>
    </main>
  )
}

// Rendered in the initial HTML while TelemetryTabs (a useSearchParams client
// tree) is client-rendered. Mirrors the session view's layout dimensions so the
// tab bar and chart land in the same place after hydration — without this the
// boundary renders empty and the whole UI pops in, causing a large layout shift.
function TelemetryTabsSkeleton() {
  return (
    <div className="px-2 mx-auto max-w-400 py-8" aria-hidden>
      <div className="flex items-end justify-between">
        <div className="rounded-xs bg-surface-card border border-white/10 p-1 mt-10 h-10! min-w-1/4" />
        <div className="rounded-xs px-4 h-10 w-28 border border-surface-border bg-surface-card" />
      </div>
      <div className="border border-surface-border bg-surface-base flex flex-col lg:flex-row items-start min-h-120 py-8 px-4 rounded-xs gap-4">
        <div className="hidden lg:block w-52 self-stretch lg:border-r lg:border-surface-border lg:pr-4" />
        <div className="flex-1 w-full flex flex-col min-w-0 gap-4">
          <div className="h-4 w-12" />
          <div className="w-full h-120 border border-surface-border bg-surface-card" />
        </div>
      </div>
    </div>
  )
}
