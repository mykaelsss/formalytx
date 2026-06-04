import { useRef } from "react";
import { ColorPicker, ColorPickerArea, ColorPickerContent, ColorPickerEyeDropper, ColorPickerFormatSelect, ColorPickerHueSlider, ColorPickerInput, ColorPickerSwatch, ColorPickerTrigger } from "./color-picker";


export default function ColorSwatch({
  color,
  onCommit,
  label,
}: {
  color: string;
  onCommit: (c: string) => void;
  label?: string;
}) {
  const pendingRef = useRef(color);

  return (
    <ColorPicker
      defaultValue={color}
      defaultFormat="hex"
      onValueChange={(v) => {
        pendingRef.current = v;
      }}
      onOpenChange={(open) => {
        if (!open) onCommit(pendingRef.current);
      }}
    >
      <ColorPickerTrigger asChild>
        <ColorPickerSwatch
          aria-label={label}
          className="size-5 rounded-sm border border-surface-border cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        />
      </ColorPickerTrigger>
      <ColorPickerContent className="bg-surface-card border-surface-border text-text-primary shadow-[0_8px_32px_rgba(0,0,0,0.6)]">
        <ColorPickerArea className="border border-surface-border" />
        <div className="flex items-center gap-2">
          <ColorPickerEyeDropper className="text-text-primary border-surface-border" />
          <div className="flex flex-1 flex-col gap-2">
            <ColorPickerHueSlider />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ColorPickerFormatSelect className="text-text-primary border-surface-border" />
          <ColorPickerInput withoutAlpha className="border-surface-border" />
        </div>
      </ColorPickerContent>
    </ColorPicker>
  );
}