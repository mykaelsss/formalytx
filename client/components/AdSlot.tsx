"use client";

import { useEffect, useRef } from "react";
import { ADSENSE_CLIENT } from "@/lib/ads";
import { cn } from "@/lib/utils";

declare global {
  interface Window {
    adsbygoogle?: unknown[];
  }
}

const isProduction = process.env.NODE_ENV === "production";

interface AdSlotProps {
  slot: string;
  className?: string;
}

// A single horizontal display unit. The min-height reserves space up front so
// the ad filling in doesn't shift surrounding content.
export default function AdSlot({ slot, className }: AdSlotProps) {
  const insRef = useRef<HTMLModElement>(null);

  useEffect(() => {
    if (!isProduction || !slot) return;
    // Strict mode runs effects twice; AdSense throws if a unit is pushed twice.
    if (insRef.current?.dataset['adsbygoogleStatus']) return;
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch (err) {
      console.error(err);
    }
  }, [slot]);

  if (isProduction && !slot) return null;

  return (
    <aside aria-label="Advertisement" className={cn("flex flex-col gap-2", className)}>
      <span className="font-mono text-[9px] tracking-[0.25em] uppercase text-text-muted">
        Advertisements
      </span>
      {isProduction ? (
        <ins
          ref={insRef}
          className="adsbygoogle block min-h-[90px] w-full"
          data-ad-client={ADSENSE_CLIENT}
          data-ad-slot={slot}
          data-ad-format="horizontal"
          data-full-width-responsive="true"
        />
      ) : (
        <div className="flex min-h-[90px] w-full items-center justify-center border border-dashed border-surface-border bg-surface-card/40 font-mono text-[10px] tracking-[0.2em] uppercase text-text-muted">
          Ad placeholder · {slot || "no slot id"}
        </div>
      )}
    </aside>
  );
}
