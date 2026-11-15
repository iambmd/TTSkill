/**
 * Rubber recommender, a TypeScript port of backend/equipment/recommend.py so the page also works
 * without the backend (stub and demo mode). Data: PingSense (github.com/iambmd/Pingsense), see
 * backend/equipment/SOURCE.md. Keep the rules here and in recommend.py in step.
 */
import data from "./rubbers.json";

export const STYLES = ["spin", "speed"] as const;
export const TYPES = ["inverted", "short_pips", "long_pips", "anti_spin"] as const;
export const LEVELS = ["beginner", "intermediate", "advanced"] as const;
export type Style = (typeof STYLES)[number];
export type RubberType = (typeof TYPES)[number];
export type Level = (typeof LEVELS)[number];

export type Rubber = {
  name: string; brand: string; price: number | null; speed: number | null; spin: number | null;
  control: number | null; hardness: number | null; overall: number | null; type: string;
};
export type Recommendation = {
  style: Style; type: RubberType; level: Level; thickness: string; results: Rubber[]; note: string | null;
};

// Thinner sponge as the level goes down: slower and easier to control.
export const THICKNESS: Record<RubberType, Record<Level, string>> = {
  inverted: { advanced: "2.1 mm or max", intermediate: "1.8-2.0 mm", beginner: "1.5-1.8 mm" },
  short_pips: { advanced: "2.0 mm or max", intermediate: "1.8-2.0 mm", beginner: "1.5-1.8 mm" },
  long_pips: { advanced: "1.0-1.5 mm", intermediate: "0.5-1.0 mm", beginner: "OX (no sponge) to 0.5 mm" },
  anti_spin: { advanced: "1.5-2.0 mm", intermediate: "1.0-1.5 mm", beginner: "0.5-1.0 mm" },
};
const LEVEL_RULES: Record<Level, { lo: number; hi: number; minControl: number }> = {
  beginner: { lo: 0, hi: 9.0, minControl: 8.5 },
  intermediate: { lo: 8.5, hi: 9.4, minControl: 8.0 },
  advanced: { lo: 9.0, hi: 10, minControl: 0 },
};
const MIN_OVERALL = 8.0;
const PRICE_BAND = 5;

const RUBBERS = data as Rubber[];

/** Cheapest $5 price band first, then the highest user score (Overall). */
export function recommend(style: Style, type: RubberType, level: Level, limit = 8): Recommendation {
  const rule = LEVEL_RULES[level];
  const picks = RUBBERS.filter((r) => {
    if (r.type !== type || r.price === null || (r.overall ?? 0) < MIN_OVERALL) return false;
    if (r.control !== null && r.control < rule.minControl) return false;
    if (type === "anti_spin") return true; // anti ratings for speed/spin are all low by design
    const v = r[style] ?? 0;
    return rule.lo <= v && v <= rule.hi;
  });
  const key = (r: Rubber) => [Math.floor(r.price! / PRICE_BAND), -(r.overall ?? 0), -(r[style] ?? 0)];
  picks.sort((a, b) => {
    const [x, y] = [key(a), key(b)];
    return x[0] - y[0] || x[1] - y[1] || x[2] - y[2];
  });
  const note = type === "short_pips" || type === "long_pips"
    ? "PingSense has no pips rubbers yet, so there is nothing to rank. They're on the list."
    : null;
  return { style, type, level, thickness: THICKNESS[type][level], results: picks.slice(0, limit), note };
}
