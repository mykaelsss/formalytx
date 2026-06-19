import { CompoundColor, CompoundColor2018, CompoundLetter } from "@/lib/compounds";
import { Compound } from "@/lib/types";

export default function TyreBadge({
  compound,
  size = 20,
  year = "2026",
}: {
  compound: Compound;
  size?: number;
  year?: string;
}) {
  const color =
    (year === "2018"
      ? { ...CompoundColor, ...CompoundColor2018 }
      : CompoundColor)[compound] ?? "oklch(94.01% 0.000 0)";
  const letter = CompoundLetter[compound] ?? "?";
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 172 172"
      fill="none"
    >
      <circle cx="86" cy="86" r="86" fill="black" />
      <path
        d="M70 19C40.68 26.58 19 53.48 19 85.5C19 117.52 40.68 144.42 70 152"
        stroke={color}
        strokeWidth="14"
      />
      <path
        d="M101 152C130.32 144.42 152 117.52 152 85.5C152 53.48 130.32 26.58 101 19"
        stroke={color}
        strokeWidth="14"
      />
      <text
        x="86"
        y="86"
        textAnchor="middle"
        dominantBaseline="central"
        fill="white"
        fontSize={letter.length > 1 ? 62 : 68}
        fontWeight="700"
        fontFamily="sans-serif"
      >
        {letter}
      </text>
    </svg>
  );
}