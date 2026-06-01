import { Compound } from "./types";

export const CompoundColor: Record<Compound, string> = {
  HYPERSOFT: "oklch(84.36% 0.091 2.81)",
  ULTRASOFT: "oklch(58.08% 0.174 332.26)",
  SUPERSOFT: "oklch(64.53% 0.240 27.31)",
  SOFT: "oklch(58.71% 0.237 23.71)",
  MEDIUM: "oklch(94.12% 0.200 105.69)",
  HARD: "oklch(94.01% 0.000 0)",
  SUPERHARD: "oklch(73.37% 0.171 44.77)",
  INTERMEDIATE: "oklch(68.22% 0.183 145.39)",
  WET: "oklch(56.53% 0.240 260.68)",
};

export const CompoundColor2018: Partial<Record<Compound, string>> = {
  SOFT: "oklch(94.12% 0.200 105.69/ 0.5)",
  MEDIUM: "oklch(94.01% 0.000 0)",
  HARD: "oklch(68.29% 0.163 242.29)",
};

export const CompoundLetter: Record<Compound, string> = {
  HYPERSOFT: "HS",
  ULTRASOFT: "U",
  SUPERSOFT: "SS",
  SOFT: "S",
  MEDIUM: "M",
  HARD: "H",
  SUPERHARD: "SH",
  INTERMEDIATE: "I",
  WET: "W",
};

export const getCompoundColor = (compound: Compound, year: string) => {
  const key = compound.toUpperCase() as Compound;
  return (
    (year === "2018"
      ? { ...CompoundColor, ...CompoundColor2018 }
      : CompoundColor)[key] ?? "oklch(94.01% 0.000 0)"
  );
};