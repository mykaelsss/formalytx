import TelemetryTabs from "@/components/telemetry/TelemetryTabs";

export default async function TelemetryPage({ 
  searchParams
}: {
  searchParams: Promise<{ tab?: string; year?: string; round?: string; session?: string }>
}) {

  const params = await searchParams;
  const tab = params.tab ?? "session";

  return (
    <main>
      <TelemetryTabs activeTab={tab} />
    </main>
  )
}
