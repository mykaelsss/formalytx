import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  ChevronRight,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import Marquee from "react-fast-marquee";

export const metadata: Metadata = {
  title: "Formalytx · F1 Telemetry Explorer",
  description:
    "Explore Formula 1 seasons, events, sessions, driver laps, and raw car telemetry — powered by FastF1.",
};

const steps = [
  { label: "Year", color: "var(--data-blue)" },
  { label: "Event", color: "var(--data-violet)" },
  { label: "Session", color: "var(--data-amber)" },
  { label: "Drivers", color: "var(--data-cyan)" },
  { label: "Telemetry", color: "var(--accent-green)" },
];

const features = [
  {
    num: "01",
    color: "var(--data-blue)",
    tag: "SEASONS · EVENTS · SESSIONS",
    title: "Browse every race weekend",
    body: "Jump into any season, pick a Grand Prix, and load practice, qualifying, sprint, or race sessions in a couple of clicks.",
  },
  {
    num: "02",
    color: "var(--data-amber)",
    tag: "LAPS · STINTS · DELTAS",
    title: "Compare driver laps",
    body: "Select the drivers you care about, line their laps up side by side, and spot exactly where the time is won and lost.",
  },
  {
    num: "03",
    color: "var(--accent-green)",
    tag: "SPEED · THROTTLE · BRAKE · RPM · GEAR · DRS",
    title: "Inspect raw telemetry",
    body: "Plot the same channels the pit wall watches, corner by corner — straight from the car to your screen.",
  },
];

const channels = [
  { label: "SPD", value: "342", unit: "km/h" },
  { label: "THR", value: "100", unit: "%" },
  { label: "BRK", value: "0", unit: "%" },
  { label: "GEAR", value: "8", unit: "" },
  { label: "RPM", value: "11,952", unit: "" },
  { label: "DRS", value: "OPEN", unit: "" },
];

const circuits = [
  "MONZA",
  "SPA-FRANCORCHAMPS",
  "SUZUKA",
  "SILVERSTONE",
  "MONACO",
  "INTERLAGOS",
  "ZANDVOORT",
  "MARINA BAY",
  "BAKU",
  "AUSTIN",
  "JEDDAH",
  "MELBOURNE",
];

function TraceChart() {
  return (
    <svg
      viewBox="0 0 640 310"
      className="w-full h-auto block"
      role="img"
      aria-label="Sample telemetry chart showing speed, throttle, and brake traces for two drivers across one lap"
    >
      {[44, 80, 116, 152].map((y) => (
        <line
          key={y}
          x1="16"
          y1={y}
          x2="624"
          y2={y}
          stroke="var(--surface-border)"
          strokeWidth="1"
          strokeDasharray="2 4"
        />
      ))}

      {[219, 421].map((x) => (
        <line
          key={x}
          x1={x}
          y1="14"
          x2={x}
          y2="292"
          stroke="var(--surface-border)"
          strokeWidth="1"
        />
      ))}
      <text x="112" y="20" fill="var(--text-muted)" fontSize="9" fontFamily="var(--font-roboto-mono)" textAnchor="middle">S1</text>
      <text x="320" y="20" fill="var(--text-muted)" fontSize="9" fontFamily="var(--font-roboto-mono)" textAnchor="middle">S2</text>
      <text x="522" y="20" fill="var(--text-muted)" fontSize="9" fontFamily="var(--font-roboto-mono)" textAnchor="middle">S3</text>

      <text x="16" y="38" fill="var(--text-muted)" fontSize="9" fontFamily="var(--font-roboto-mono)" letterSpacing="2">SPEED</text>
      <text x="16" y="193" fill="var(--text-muted)" fontSize="9" fontFamily="var(--font-roboto-mono)" letterSpacing="2">THROTTLE</text>
      <text x="16" y="249" fill="var(--text-muted)" fontSize="9" fontFamily="var(--font-roboto-mono)" letterSpacing="2">BRAKE</text>

      <path
        d="M16 76 L94 58 L126 53 L134 56 L141 102 L149 156 L161 164 L170 158 L178 138 L198 114 L232 84 L270 70 L288 68 L298 72 L310 118 L320 134 L332 130 L354 102 L392 76 L422 68 L434 70 L446 116 L458 146 L470 150 L482 134 L502 106 L542 78 L592 58 L624 52"
        fill="none"
        stroke="var(--data-violet)"
        strokeWidth="1.5"
        strokeDasharray="7 5"
        className="animate-fade-in"
        style={{ animationDelay: "1.4s", animationDuration: "800ms", animationFillMode: "both" }}
      />
      <path
        d="M16 70 L96 52 L128 48 L136 50 L142 96 L150 150 L160 158 L168 154 L176 132 L196 108 L230 78 L268 64 L286 62 L296 66 L308 112 L318 128 L330 124 L352 96 L390 70 L420 62 L432 64 L444 110 L456 140 L468 144 L480 128 L500 100 L540 72 L590 52 L624 46"
        fill="none"
        stroke="var(--accent-green)"
        strokeWidth="2"
        strokeLinejoin="round"
        pathLength={1}
        className="trace-draw"
      />

      <path
        d="M16 200 L130 200 L138 230 L158 230 L166 218 L186 206 L200 200 L300 200 L308 226 L324 226 L334 200 L436 200 L444 228 L462 228 L476 210 L488 200 L624 200"
        fill="none"
        stroke="var(--data-blue)"
        strokeWidth="1.5"
        strokeLinejoin="round"
        pathLength={1}
        className="trace-draw"
        style={{ animationDelay: "400ms" }}
      />

      <path
        d="M16 286 L126 286 L132 254 L152 254 L160 286 L298 286 L304 256 L320 256 L328 286 L432 286 L438 255 L456 255 L464 286 L624 286"
        fill="none"
        stroke="var(--accent-red)"
        strokeWidth="1.5"
        strokeLinejoin="round"
        pathLength={1}
        className="trace-draw"
        style={{ animationDelay: "700ms" }}
      />
    </svg>
  );
}

function SectionLabel({ id, title, right }: { id: string; title: string; right?: string }) {
  return (
    <div className="flex items-center gap-4">
      <span className="font-mono text-[10px] tracking-[0.25em] uppercase text-accent-green shrink-0">
        {id}
      </span>
      <span className="font-mono text-[10px] tracking-[0.25em] uppercase text-text-muted shrink-0">
        {title}
      </span>
      <div className="flex-1 h-px bg-surface-border" />
      {right && (
        <span className="font-mono text-[10px] tracking-[0.25em] uppercase text-text-muted shrink-0 max-sm:hidden">
          {right}
        </span>
      )}
    </div>
  );
}

export default function Home() {
  return (
    <main className="flex flex-col">

      {/* ── Hero ── */}
      <section className="relative w-full overflow-hidden border-b border-surface-border">
        <div
          className="landing-grid absolute inset-0 pointer-events-none"
          style={{ maskImage: "radial-gradient(ellipse 90% 90% at 50% 0%, black 25%, transparent 75%)" }}
        />
        <div
          className="absolute -top-44 right-[-12%] size-130 rounded-full pointer-events-none opacity-25"
          style={{ background: "radial-gradient(circle, var(--accent-green-dark), transparent 65%)" }}
        />
        <span
          aria-hidden
          className="text-ghost-outline absolute -bottom-7 left-0 font-black italic uppercase tracking-tight leading-none text-[clamp(6rem,17vw,16rem)] whitespace-nowrap pointer-events-none select-none opacity-60"
        >
          Telemetry
        </span>

        <div className="relative mx-auto max-w-6xl px-5">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3 border-b border-surface-border font-mono text-[10px] tracking-[0.2em] uppercase text-text-muted">
            <span>FRMLX // Telemetry Explorer</span>
            <span className="flex items-center gap-2">
              <span className="size-1.5 rounded-full bg-accent-green shrink-0 animate-pulse" />
              Data: FastF1 · 2018 →
            </span>
          </div>

          <div className="grid gap-12 lg:grid-cols-12 lg:items-end pt-14 pb-20 lg:pt-20 lg:pb-28">
            <div
              className="lg:col-span-7 flex flex-col items-start gap-8 animate-fade-in"
              style={{ animationDuration: "600ms", animationFillMode: "both" }}
            >
              <span className="font-mono text-[10px] tracking-[0.3em] uppercase text-text-muted">
                [ F1 Telemetry Explorer · Every lap · Every channel ]
              </span>

              <h1 className="font-black italic uppercase text-text-primary tracking-tight leading-[0.92] text-[clamp(3.25rem,8vw,6.5rem)]">
                Formula 1
                <br />
                data,{" "}
                <span className="text-accent-green">
                  decoded.
                </span>
              </h1>

              <p className="text-text-secondary text-base sm:text-lg leading-relaxed max-w-md">
                Navigate F1 seasons, events, and sessions — then dive into
                driver laps and raw car telemetry, all in one place.
              </p>

              <div className="flex flex-wrap items-center gap-3">
                <Button
                  asChild
                  className="rounded-none h-12 px-7 text-xs font-semibold uppercase tracking-[0.15em] cursor-pointer bg-accent-green text-black hover:bg-accent-green-hover! [clip-path:polygon(0_0,100%_0,100%_calc(100%-12px),calc(100%-12px)_100%,0_100%)]"
                >
                  <Link href="/telemetry">
                    Launch Explorer
                    <ArrowRight />
                  </Link>
                </Button>
              </div>
            </div>

            <div
              className="lg:col-span-5 animate-fade-in"
              style={{ animationDelay: "150ms", animationDuration: "600ms", animationFillMode: "both" }}
            >
              <div className="border border-surface-border bg-surface-card shadow-[0_24px_80px_-32px_rgba(0,0,0,0.9)]">
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5 px-4 py-2.5 border-b border-surface-border">
                  <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.2em] uppercase text-text-muted">
                    <span className="size-1.5 rounded-full bg-accent-green animate-pulse" />
                    Monza · Q3
                  </div>
                  <div className="flex items-center gap-4 font-mono text-[10px] tabular-nums">
                    <span className="flex items-center gap-1.5 text-text-secondary">
                      <span className="inline-block w-4 border-t-2" style={{ borderColor: "var(--accent-green)" }} />
                      VER 1:19.327
                    </span>
                    <span className="flex items-center gap-1.5 text-text-muted">
                      <span className="inline-block w-4 border-t-2 border-dashed" style={{ borderColor: "var(--data-violet)" }} />
                      LEC +0.142
                    </span>
                  </div>
                </div>

                <div className="px-3 py-4">
                  <TraceChart />
                </div>

                <div className="grid grid-cols-3 sm:grid-cols-6 border-t border-surface-border">
                  {channels.map((ch, i) => (
                    <div
                      key={ch.label}
                      className={`flex flex-col gap-0.5 px-3 py-2.5 border-surface-border ${i > 0 ? "border-l" : ""} ${i >= 3 ? "max-sm:border-t max-sm:nth-4:border-l-0" : ""}`}
                    >
                      <span className="font-mono text-[9px] tracking-[0.2em] text-text-muted">{ch.label}</span>
                      <span className="font-mono text-xs text-text-primary tabular-nums">
                        {ch.value}
                        {ch.unit && <span className="text-text-muted ml-1 text-[9px]">{ch.unit}</span>}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
              <p className="mt-2.5 font-mono text-[10px] tracking-[0.2em] uppercase text-text-muted text-right">
                Fig. 01 — Speed / Throttle / Brake
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Circuit ticker ── */}
      <section className="w-full border-b border-surface-border bg-surface-card/40 overflow-hidden select-none" aria-hidden>
        <Marquee className="flex w-max items-center py-3" speed={60}>
            <div className="flex items-center shrink-0">
              {circuits.map((circuit) => (
                <span
                  key={circuit}
                  className="flex items-center font-mono text-[11px] tracking-[0.3em] uppercase text-text-muted"
                >
                  <span className="px-6">{circuit}</span>
                  <span className="size-1 rotate-45 bg-accent-green-dark shrink-0" />
                </span>
              ))}
            </div>
        </Marquee>
      </section>

      {/* ── Step rail ── */}
      <section className="w-full border-b border-surface-border">
        <div
          className="mx-auto max-w-6xl px-5 py-12 flex flex-col gap-8 animate-fade-in"
          style={{ animationDelay: "250ms", animationDuration: "600ms", animationFillMode: "both" }}
        >
          <SectionLabel id="001" title="Selection flow" right="One sidebar · One flow" />

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-0">
            {steps.map((step, i) => (
              <div key={step.label} className="flex items-center sm:flex-1">
                <span className="font-mono text-[10px] text-text-muted tabular-nums mr-2.5">
                  0{i + 1}
                </span>
                <span
                  className="font-mono text-[11px] font-semibold tracking-widest uppercase px-3 py-1.5 border"
                  style={{
                    color: step.color,
                    borderColor: step.color,
                    background: `color-mix(in oklch, ${step.color} 10%, transparent)`,
                  }}
                >
                  {step.label}
                </span>
                <div className="flex-1 h-px bg-surface-border mx-2" />
                {i < steps.length - 1 ? (
                  <ChevronRight className="size-3 text-text-muted shrink-0 sm:mr-2 max-sm:rotate-90" />
                ) : (
                  <span className="size-1.5 rotate-45 bg-accent-green shrink-0 max-sm:mr-0.5" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Capability index ── */}
      <section className="w-full border-b border-surface-border">
        <div
          className="mx-auto max-w-6xl px-5 py-12 flex flex-col gap-2 animate-fade-in"
          style={{ animationDelay: "350ms", animationDuration: "600ms", animationFillMode: "both" }}
        >
          <SectionLabel id="002" title="Capability index" />

          <div className="flex flex-col">
            {features.map((feature, i) => (
              <div
                key={feature.num}
                className={`group relative grid gap-4 lg:grid-cols-[120px_1.1fr_1fr] lg:items-baseline py-9 transition-colors duration-200 hover:bg-surface-card ${i > 0 ? "border-t border-surface-border" : ""}`}
                style={{ ["--feature-color" as string]: feature.color }}
              >
                <div
                  className="absolute left-0 top-0 h-full w-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                  style={{ background: "var(--feature-color)" }}
                />

                <span className="font-mono font-bold text-4xl lg:text-5xl text-text-disabled tabular-nums leading-none lg:pl-5">
                  {feature.num}
                </span>

                <div className="flex flex-col gap-3 lg:pl-2">
                  <span
                    className="font-mono text-[10px] tracking-[0.25em] uppercase"
                    style={{ color: "var(--feature-color)" }}
                  >
                    {feature.tag}
                  </span>
                  <h2 className="text-text-primary font-bold text-2xl lg:text-[28px] leading-tight tracking-tight">
                    {feature.title}
                  </h2>
                </div>

                <p className="text-text-secondary text-sm sm:text-base leading-relaxed lg:pr-5">
                  {feature.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FastF1 Credit ── */}
      <section className="w-full border-b border-surface-border">
        <div
          className="mx-auto max-w-6xl px-5 py-12 flex flex-col gap-8 animate-fade-in"
          style={{ animationDelay: "450ms", animationDuration: "600ms", animationFillMode: "both" }}
        >
          <SectionLabel id="A" title="Appendix — Data source" />

          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
            <div className="flex flex-col gap-2">
              <span className="font-mono text-sm font-semibold text-accent-green">
                FastF1
              </span>
              <p className="text-text-secondary text-sm leading-relaxed max-w-lg">
                All data is sourced through{" "}
                <span className="text-text-primary font-medium">FastF1</span> — an
                open-source Python library built by{" "}
                <span className="text-text-primary font-medium">Philipp Schaefer</span> and
                the open-source community. Full credit to their work.
              </p>
            </div>

            <Button
              asChild
              variant="outline"
                className="text-xs cursor-pointer text-accent-green border-surface-border bg-surface-card p-4 h-11 rounded-none hover:bg-surface-card-hover hover:text-accent-green"
            >
              <Link href="https://docs.fastf1.dev" target="_blank" rel="noopener noreferrer">
                FastF1 Docs
                <ExternalLink />
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* ── Bottom CTA ── */}
      <section className="w-full relative overflow-hidden">
        <div className="kerb-stripe h-2.5 w-full opacity-80" aria-hidden />
        <Link
          href="/telemetry"
          className="group relative block focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent-green"
        >
          <div
            className="landing-grid absolute inset-0 pointer-events-none"
            style={{ maskImage: "radial-gradient(ellipse 70% 100% at 50% 100%, black 20%, transparent 80%)" }}
          />
          <div className="relative mx-auto max-w-6xl px-5 py-16 lg:py-24 flex flex-col gap-5">
            <span className="font-mono text-[10px] tracking-[0.3em] uppercase text-text-muted">
              [ No setup · No notebooks · Just data ]
            </span>
            <span className="flex flex-wrap items-center gap-x-6 gap-y-2 font-black italic uppercase tracking-tight leading-none text-[clamp(2.75rem,7.5vw,6rem)] text-text-primary transition-colors duration-200 group-hover:text-accent-green">
              Start exploring
              <ArrowRight
                className="size-[0.7em] shrink-0 transition-transform duration-300 group-hover:translate-x-3"
                strokeWidth={2.5}
              />
            </span>
          </div>
        </Link>
      </section>
    </main>
  );
}
