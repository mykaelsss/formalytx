"use client";

import { Settings } from "lucide-react";
import { useState } from "react";
import { m, AnimatePresence } from "motion/react";
import type { PointSymbol, TelemetryChannelSettings } from "@/lib/types";
import { defaultTelemetryChannelSettings, defaultTelemetrySettings } from "@/lib/utils";
import { setTelemetrySettings, useTelemetrySettings } from "@/lib/hooks/useTelemetrySettings";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { CHANNELS } from "@/lib/constants";

const CHANNEL_LABELS: Record<string, string> = {
  speed: "Spd",
  throttle: "Thr",
  brake: "Brk",
  rpm: "RPM",
  gear: "Gear",
  delta: "Delta",
};

function ChannelSettingsForm({
  settings,
  onChange,
}: {
  settings: TelemetryChannelSettings;
  onChange: (s: TelemetryChannelSettings) => void;
}) {
  return (
    <div className="flex flex-col gap-4 text-sm">
      <div className="flex items-center justify-between">
        <Label>Smooth Lines</Label>
        <Switch
          checked={settings.smooth}
          onCheckedChange={(v) => onChange({ ...settings, smooth: v })}
          className="cursor-pointer data-[state=checked]:bg-muted-foreground"
        />
      </div>
      <div className="flex items-center justify-between">
        <Label>Show Symbols</Label>
        <Switch
          checked={settings.showSymbol}
          onCheckedChange={(v) => onChange({ ...settings, showSymbol: v })}
          className="cursor-pointer data-[state=checked]:bg-muted-foreground"
        />
      </div>
      {settings.showSymbol && (
        <>
          <div className="flex items-center justify-between">
            <Label>Point Style</Label>
            <Select
              value={settings.symbol}
              onValueChange={(v) => onChange({ ...settings, symbol: v as PointSymbol })}
            >
              <SelectTrigger className="w-32 text-text-primary border-surface-border">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-surface-card text-text-primary">
                <SelectItem value="circle">Circle</SelectItem>
                <SelectItem value="rect">Square</SelectItem>
                <SelectItem value="triangle">Triangle</SelectItem>
                <SelectItem value="diamond">Diamond</SelectItem>
                <SelectItem value="roundRect">Rounded Square</SelectItem>
                <SelectItem value="pin">Pin</SelectItem>
                <SelectItem value="arrow">Arrow</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-2">
            <div className="flex justify-between">
              <p>Point Size</p>
              <p className="text-text-muted">{settings.symbolSize}</p>
            </div>
            <Slider
              value={[settings.symbolSize]}
              onValueChange={([v]) => onChange({ ...settings, symbolSize: v ?? 1})}
              min={1}
              max={15}
              step={1}
            />
          </div>
        </>
      )}
      <div className="flex flex-col gap-2">
        <div className="flex justify-between">
          <p>Line Width</p>
          <p className="text-text-muted">{settings.lineWidth}</p>
        </div>
        <Slider
          value={[settings.lineWidth]}
          onValueChange={([v]) => onChange({ ...settings, lineWidth: v ?? 1})}
          min={1}
          max={5}
          step={1}
        />
      </div>
    </div>
  );
}

export default function TelemetrySettingsPanel() {
  const settings = useTelemetrySettings();
  const [activeTab, setActiveTab] = useState("speed");
  const [direction, setDirection] = useState(1);

  const handleTabChange = (val: string) => {
    const prevIdx = CHANNELS.indexOf(activeTab as typeof CHANNELS[number]);
    const nextIdx = CHANNELS.indexOf(val as typeof CHANNELS[number]);
    setDirection(nextIdx >= prevIdx ? 1 : -1);
    setActiveTab(val);
  };

  const isDefault =
    settings.useGlobalSettings &&
    Object.keys(defaultTelemetryChannelSettings).every(
      (k) =>
        settings.global[k as keyof TelemetryChannelSettings] ===
        defaultTelemetryChannelSettings[k as keyof TelemetryChannelSettings],
    );

  const updateGlobal = (global: TelemetryChannelSettings) =>
    setTelemetrySettings({ ...settings, global });

  const updateChannel = (channel: string, ch: TelemetryChannelSettings) =>
    setTelemetrySettings({ ...settings, channels: { ...settings.channels, [channel]: ch } });

  const getChannelSettings = (channel: string) =>
    settings.channels[channel] ?? defaultTelemetryChannelSettings;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" className="shrink-0">
          <Settings className="size-4.5 text-text-muted hover:text-text-primary transition-colors cursor-pointer" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="w-72 bg-surface-card text-text-primary flex flex-col gap-4 shadow-[0_8px_32px_rgba(0,0,0,0.6)]"
        align="end"
        side="bottom"
      >
        <div className="flex items-center justify-between text-sm">
          <Label>Global Settings</Label>
          <Switch
            checked={settings.useGlobalSettings}
            onCheckedChange={(v) =>
              setTelemetrySettings({ ...settings, useGlobalSettings: v })
            }
            className="cursor-pointer data-[state=checked]:bg-muted-foreground"
          />
        </div>

        {settings.useGlobalSettings ? (
          <ChannelSettingsForm settings={settings.global} onChange={updateGlobal} />
        ) : (
          <Tabs value={activeTab} onValueChange={handleTabChange}>
            <TabsList className="relative flex rounded-xs bg-surface-base border border-white/10 p-1 gap-0 w-full h-auto">
              {CHANNELS.map((ch) => (
                <TabsTrigger
                  key={ch}
                  value={ch}
                  className="relative z-10 flex-1 py-1 px-0 text-xs text-text-primary/50 bg-none! data-active:bg-none! data-active:text-accent-green transition-colors cursor-pointer hover:text-text-primary"
                >
                  {activeTab === ch && (
                    <m.div
                      layoutId="telemetry-settings-tab-bg"
                      className="absolute inset-0.5 rounded-sm border border-accent-green/40"
                      transition={{ type: "spring", stiffness: 400, damping: 30 }}
                    />
                  )}
                  <span className="relative z-10">{CHANNEL_LABELS[ch]}</span>
                </TabsTrigger>
              ))}
            </TabsList>

            <div className="overflow-x-clip pt-3">
              <AnimatePresence mode="popLayout" initial={false} custom={direction}>
                {CHANNELS.map((ch) =>
                  ch === activeTab ? (
                    <TabsContent key={ch} value={ch} forceMount asChild>
                      <m.div
                        key={ch}
                        custom={direction}
                        initial={{ x: direction * 24, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: direction * -24, opacity: 0 }}
                        transition={{ type: "spring", stiffness: 400, damping: 35 }}
                      >
                        <ChannelSettingsForm
                          settings={getChannelSettings(ch)}
                          onChange={(s) => updateChannel(ch, s)}
                        />
                      </m.div>
                    </TabsContent>
                  ) : null
                )}
              </AnimatePresence>
            </div>
          </Tabs>
        )}

        {!isDefault && (
          <>
            <hr className="w-9/10 mx-auto border-surface-border" />
            <Button
              size="sm"
              variant="outline"
              className="text-xs cursor-pointer text-accent-green border-surface-border bg-surface-card py-4 rounded-none hover:bg-surface-card-hover hover:text-accent-green"
              onClick={() => setTelemetrySettings(defaultTelemetrySettings)}
            >
              Reset Settings
            </Button>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
