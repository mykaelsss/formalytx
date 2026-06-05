import SVGLogo from "@/components/ui/SVGLogo";
import type { Metadata } from "next";
import Link from "next/link";
import { Activity, ExternalLink, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

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

export default function Home() {
  return (
    <main className="flex flex-col items-center px-5 pt-10 pb-28 gap-18">

      {/* ── Logo ── */}
      <div
        className="w-full max-w-lg animate-fade-in"
        style={{ animationFillMode: "both", animationDuration: "600ms" }}
      >
        <SVGLogo />
      </div>

      {/* ── Hero ── */}
      <section
        className="text-center max-w-2xl flex flex-col items-center gap-7 animate-fade-in"
        style={{ animationDelay: "100ms", animationFillMode: "both", animationDuration: "600ms" }}
      >
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-surface-border bg-surface-card text-text-muted text-[10px] font-mono tracking-[0.2em] uppercase select-none">
          <span className="size-1.5 rounded-full bg-accent-green shrink-0" />
          Powered by FastF1
        </div>

        <h1 className="text-4xl sm:text-[52px] font-bold text-text-primary leading-[1.1] tracking-tight">
          Formula 1 data,{" "}
          <br className="hidden sm:block" />
          <span className="text-accent-green">decoded.</span>
        </h1>

        <p className="text-text-secondary text-base sm:text-lg leading-relaxed max-w-xl">
          Formalytx lets you navigate F1 seasons, events, and sessions — then
          dive into driver laps and raw car telemetry, all in one place.
        </p>

        <Button asChild className="rounded-none text-xs cursor-pointer text-accent-green border-surface-border bg-surface-card px-6 py-6 hover:bg-surface-card-hover hover:text-accent-green">
          <Link href="/telemetry">
            Get Started
            <ChevronRight />
          </Link>
        </Button>
      </section>

      {/* ── Divider ── */}
      <div
        className="w-full max-w-4xl flex items-center gap-4 animate-fade-in"
        style={{ animationDelay: "200ms", animationFillMode: "both", animationDuration: "600ms" }}
      >
        <div className="flex-1 h-px bg-surface-border" />
        <span className="font-mono text-[10px] tracking-[0.25em] uppercase text-text-muted shrink-0">
          What you can do
        </span>
        <div className="flex-1 h-px bg-surface-border" />
      </div>

      {/* ── Feature Card ── */}
      <section
        className="w-full max-w-4xl animate-fade-in"
        style={{ animationDelay: "280ms", animationFillMode: "both", animationDuration: "500ms" }}
      >
        <div className="group relative flex flex-col gap-6 p-6 rounded-xl border border-surface-border bg-surface-card hover:bg-surface-card-hover hover:border-accent-green transition-colors duration-200">
          <div className="absolute top-0 left-6 right-6 h-px rounded-full bg-accent-green opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

          <div className="size-10 rounded-lg flex items-center justify-center shrink-0 bg-accent-green/15">
            <Activity className="size-5 text-accent-green" />
          </div>

          <div className="flex flex-col gap-2">
            <h2 className="text-text-primary font-semibold text-base leading-snug">
              One tool, one flow
            </h2>
            <p className="text-text-secondary text-sm leading-relaxed max-w-2xl">
              Everything lives in a single sidebar. Pick a year and event, choose a session, select the drivers you want to compare, then plot their lap times and raw car telemetry — all without leaving the page.
            </p>
          </div>

          {/* Step flow */}
          <div className="flex items-center gap-0 flex-wrap">
            {steps.map((step, i) => (
              <div key={step.label} className="flex items-center">
                <span
                  className="font-mono text-[10px] font-semibold tracking-widest uppercase px-2.5 py-1 border"
                  style={{ color: step.color, borderColor: step.color, background: `color-mix(in oklch, ${step.color} 10%, transparent)` }}
                >
                  {step.label}
                </span>
                {i < steps.length - 1 && (
                  <ChevronRight className="size-3 text-text-muted shrink-0" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FastF1 Credit ── */}
      <section
        className="w-full max-w-4xl animate-fade-in"
        style={{ animationDelay: "540ms", animationFillMode: "both", animationDuration: "500ms" }}
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-5 p-6 rounded-xl border border-surface-border bg-surface-card">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] tracking-[0.2em] uppercase text-text-muted">
                Built on
              </span>
              <span className="font-mono text-xs font-semibold text-accent-green">
                FastF1
              </span>
            </div>
            <p className="text-text-secondary text-sm leading-relaxed max-w-lg">
              All session and telemetry data is sourced through{" "}
              <span className="text-text-primary font-medium">FastF1</span> — an
              open-source Python library built by{" "}
              <span className="text-text-primary font-medium">Philipp Schaefer</span> and
              the open-source community. Full credit to their work.
            </p>
          </div>

          <Button asChild className="rounded-none text-xs cursor-pointer text-accent-green border-surface-border bg-surface-card px-10 py-6 hover:bg-surface-card-hover hover:text-accent-green shrink-0">
            <Link href="https://docs.fastf1.dev" target="_blank" rel="noopener noreferrer">
              FastF1 Docs
              <ExternalLink />
            </Link>
          </Button>
        </div>
      </section>
    </main>
  );
}
