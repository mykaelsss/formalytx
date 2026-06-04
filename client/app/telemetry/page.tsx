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
  searchParams: Promise<{ tab?: string; year?: string; round?: string; session?: string }>
}) {

  const params = await searchParams;
  const tab = params.tab ?? "session";

  return (
    <main>
      <Suspense>
        <TelemetryTabs activeTab={tab} />
      </Suspense>
    </main>
  )
}
