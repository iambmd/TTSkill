/**
 * Rubber recommender, a TypeScript port of backend/equipment/recommend.py so the page also works
 * without the backend (stub and demo mode). Data: PingSense (github.com/iambmd/Pingsense), see
 * backend/equipment/SOURCE.md. Keep the rules here and in recommend.py in step.
 */
import data from "./rubbers.json";
import { withRubberBuyLinks, type BuyLinkData } from "./buy-links";

export const STYLES = ["spin", "speed"] as const;
export const TYPES = ["inverted", "short_pips", "long_pips", "anti_spin"] as const;
export const LEVELS = ["beginner", "intermediate", "advanced"] as const;
export type Style = (typeof STYLES)[number];
export type RubberType = (typeof TYPES)[number];
export type Level = (typeof LEVELS)[number];

export type Rubber = BuyLinkData & {
  name: string; brand: string; price: number | null; speed: number | null; spin: number | null;
  control: number | null; hardness: number | null; overall: number | null; type: string;
};
export type Recommendation = {
  style: Style; type: RubberType; level: Level; budget: number; thickness: string; results: Rubber[]; note: string | null;
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
const BAND = 10;
export const DEFAULT_BUDGET = 60;

/** 0 for (budget-10, budget], 1 for (budget-20, budget-10], ... Pricier rubbers are usually better, so band 0 ranks first. */
export const band = (price: number, budget: number) => Math.floor((budget - price) / BAND + 1e-9);

const RUBBERS = data as Rubber[];

export function rubberByName(name: string) {
  const rubber = RUBBERS.find((entry) => entry.name === name);
  return rubber && withRubberBuyLinks(rubber);
}

/** Drop rubbers over budget, then rank by budget band (closest first) and the highest user score (Overall). */
export function recommend(style: Style, type: RubberType, level: Level, budget = DEFAULT_BUDGET, limit = 8): Recommendation {
  const rule = LEVEL_RULES[level];
  const picks = RUBBERS.filter((r) => {
    if (r.type !== type || r.price === null || r.price > budget || (r.overall ?? 0) < MIN_OVERALL) return false;
    if (r.control !== null && r.control < rule.minControl) return false;
    if (type === "anti_spin") return true; // anti ratings for speed/spin are all low by design
    const v = r[style] ?? 0;
    return rule.lo <= v && v <= rule.hi;
  });
  const key = (r: Rubber) => [band(r.price!, budget), -(r.overall ?? 0), -(r[style] ?? 0)];
  picks.sort((a, b) => {
    const [x, y] = [key(a), key(b)];
    return x[0] - y[0] || x[1] - y[1] || x[2] - y[2];
  });
  const note = type === "short_pips" || type === "long_pips"
    ? "PingSense has no pips rubbers yet, so there is nothing to rank. They're on the list."
    : null;
  return { style, type, level, budget, thickness: THICKNESS[type][level], results: picks.slice(0, limit).map(withRubberBuyLinks), note };
}
