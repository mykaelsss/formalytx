// Qualitative palette for coloring laps by selection order. The first entries
// are the Okabe-Ito set (robust under the common forms of color vision
// deficiency); the remainder extend it with bright, well-separated hues that
// stay legible on the dark chart background. CVD-distinguishability is strongest
// across the first ~8; later entries prioritize mutual separation. Beyond the
// palette we fall back to golden-angle hues, which never cluster.
const PALETTE = [
  "#E69F00", // orange
  "#56B4E9", // sky blue
  "#009E73", // bluish green
  "#F0E442", // yellow
  "#0072B2", // blue
  "#D55E00", // vermillion
  "#CC79A7", // reddish purple
  "#88CCEE", // pale cyan
  "#AA4499", // magenta
  "#44AA99", // teal
  "#DDCC77", // sand
  "#EE6677", // coral
  "#BBCC33", // lime
  "#9970E0", // violet
  "#FF8FB1", // pink
];

// 360 * (1 - 1/phi): successive multiples never cluster, filling the wheel evenly.
const GOLDEN_ANGLE = 137.50776405003785;

export function lapColor(index: number): string {
  return PALETTE[index] ?? hslToHex((index * GOLDEN_ANGLE) % 360, 80, 60);
}

// Assign each key a stable palette slot. Keys already present keep their slot so
// removing one lap never recolors the others; freed slots are reused lowest-first
// so the CVD-safe head of the palette stays in play instead of drifting into the
// golden-angle fallbacks.
export function allocateColorSlots(
  prev: Record<string, number>,
  keys: string[],
): Record<string, number> {
  const next: Record<string, number> = {};
  const used = new Set<number>();
  for (const k of keys) {
    if (k in prev) {
      next[k] = prev[k]!;
      used.add(prev[k]!);
    }
  }
  let cursor = 0;
  for (const k of keys) {
    if (k in next) continue;
    while (used.has(cursor)) cursor++;
    next[k] = cursor;
    used.add(cursor);
  }
  return next;
}

function hslToHex(h: number, s: number, l: number): string {
  s /= 100;
  l /= 100;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const c = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
    return Math.round(255 * c)
      .toString(16)
      .padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}