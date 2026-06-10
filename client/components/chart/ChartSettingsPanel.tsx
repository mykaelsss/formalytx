import { Settings } from "lucide-react";
import { Dispatch, SetStateAction } from "react";
import { ChartSettings, LineStyle, PointSymbol } from "@/lib/types";
import { Switch } from "../ui/switch";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";
import { Slider } from "../ui/slider";
import { Label } from "../ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Button } from "../ui/button";
import { defaultChartSettings } from "@/lib/utils";

interface ChartSettingsPanelProps {
    settings: ChartSettings;
    setSettings: Dispatch<SetStateAction<ChartSettings>>;
}

export default function ChartSettingsPanel({
    settings,
    setSettings
}: ChartSettingsPanelProps) {
  const { outlierThreshold, smooth, showSymbol, symbol, symbolSize, lineWidth, firstDriverLineStyle, secondDriverLineStyle } = settings;

  const isDefault = Object.keys(defaultChartSettings).every(
    (k) => settings[k as keyof ChartSettings] === defaultChartSettings[k as keyof ChartSettings]
  );

    return (
        <Popover>
          <PopoverTrigger asChild>
              <button type="button" className="shrink-0">
                <Settings className="size-4.5 text-text-muted hover:text-text-primary transition-colors cursor-pointer" />
              </button>
          </PopoverTrigger>
          <PopoverContent className="w-64 bg-surface-card text-text-primary flex flex-col gap-4 shadow-[0_8px_32px_rgba(0,0,0,0.6)]" align="end" side="bottom">
            <div className="flex flex-col gap-4 text-sm">
              <div className="flex flex-col gap-3">
                <div className="flex justify-between">
                  <p>Outlier threshold</p>
                  <p className="text-text-muted">{outlierThreshold}%</p>
                </div>
                <Slider
                  value={[outlierThreshold]}
                  onValueChange={([v]) => setSettings(prev => ({...prev, outlierThreshold: v ?? 2}))}
                  min={1}
                  max={30}
                  step={1}
                  className="mx-auto w-full max-w-xs"
                />
              </div>
              <div className="flex items-center justify-between gap-2 w-full">
                <Label htmlFor="chart_smooth">Smooth Lines</Label>
                <Switch 
                id="chart_smooth" 
                checked={smooth} 
                onCheckedChange={() => setSettings(prev => ({...prev, smooth: !prev.smooth}))} 
                className="cursor-pointer data-[state=checked]:bg-muted-foreground" 
                />
              </div>
              <div className="flex items-center justify-between gap-2 w-full">
                <Label htmlFor="chart_smooth_symbol">Show Symbols</Label>
                <Switch 
                id="chart_show_symbol" 
                checked={showSymbol} 
                onCheckedChange={() => setSettings(prev => ({...prev, showSymbol: !prev.showSymbol}))} 
                className="cursor-pointer data-[state=checked]:bg-muted-foreground" 
                />
              </div>
              {showSymbol && (
                <>
                  <div className="flex items-center justify-between">
                    <Label>Point style</Label>
                    <Select value={symbol} onValueChange={(v) => setSettings(prev => ({...prev, symbol: v as PointSymbol}))}>
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
                  <div className="flex flex-col gap-3">
                    <div className="flex justify-between">
                      <p>Point Size</p>
                      <p className="text-text-muted">{symbolSize}</p>
                    </div>
                    <Slider
                      value={[symbolSize]}
                      onValueChange={([v]) => setSettings(prev => ({...prev, symbolSize: v ?? prev.symbolSize}))}
                      min={1}
                      max={15}
                      step={1}
                      className="mx-auto w-full max-w-xs"
                    />
                  </div>
                </>
              )}
              <div className="flex flex-col gap-3">
                <div className="flex justify-between">
                  <p>Line Width</p>
                  <p className="text-text-muted">{lineWidth}</p>
                </div>
                <Slider
                  value={[lineWidth]}
                  onValueChange={([v]) => setSettings(prev => ({...prev, lineWidth: v ?? prev.lineWidth}))}
                  min={1}
                  max={5}
                  step={1}
                  className="mx-auto w-full max-w-xs"
                />
              </div>
              <div className="flex items-center justify-between">
                <Label>First Driver Line Style</Label>
                <Select value={firstDriverLineStyle} onValueChange={(v) => setSettings(prev => ({...prev, firstDriverLineStyle: v as LineStyle}))}>
                  <SelectTrigger className="w-32 text-text-primary border-surface-border">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-surface-card text-text-primary">
                    <SelectItem value="solid">Solid</SelectItem>
                    <SelectItem value="dashed">Dashed</SelectItem>
                    <SelectItem value="dotted">Dotted</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center justify-between">
                <Label>Second Driver Line Style</Label>
                <Select value={secondDriverLineStyle} onValueChange={(v) => setSettings(prev => ({...prev, secondDriverLineStyle: v as LineStyle}))}>
                  <SelectTrigger className="w-32 text-text-primary border-surface-border">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-surface-card text-text-primary">
                    <SelectItem value="solid">Solid</SelectItem>
                    <SelectItem value="dashed">Dashed</SelectItem>
                    <SelectItem value="dotted">Dotted</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {!isDefault && (
              <>
                <hr className="w-9/10 mx-auto"/>
                <Button
                size="sm"
                variant="outline"
                className="text-xs cursor-pointer text-accent-green border-surface-border bg-surface-card py-4 rounded-none hover:bg-surface-card-hover hover:text-accent-green"
                onClick={() => setSettings(defaultChartSettings)}
                >
                  Reset Settings
                </Button>
              </>
              )}
            </div>
          </PopoverContent>
        </Popover>
    )
}