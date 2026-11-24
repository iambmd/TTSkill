/**
 * Blade recommender, the blade twin of lib/rubbers.ts: same logic (drop what is over budget, rank in budget steps,
 * best rated first), run on the bundled data so it works without the backend.
 * Data: backend/equipment/blades.json (RevSpin ratings, numbers only; specs from makers and US stores), see
 * backend/equipment/SOURCE.md. A field no source states is null, and nothing here guesses it.
 */
import data from "./blades.json";
import { bladeBuyLinks } from "./buy-links";
import {
  BAND, DEFAULT_BUDGET, HANDLE_FILTERS, bladeAllowance,
  type Blade, type BladeLevel, type BladeRecommendation, type BladeStyle, type Combo, type Feel, type HandleFilter, type Layers,
} from "./blade-types";
import { recommend as recommendRubbers } from "./rubbers";

export * from "./blade-types";

// Per level the blade's speed rating must sit in [lo, hi] and control must reach minControl, like the rubber rules.
// Beginners also skip fast carbon blades: they are hard to keep on the table. Advanced players get the fast end.
const LEVEL_RULES: Record<BladeLevel, { lo: number; hi: number; minControl: number; fastCarbon: number }> = {
  beginner: { lo: 0, hi: 8.8, minControl: 8.5, fastCarbon: 8.5 },
  intermediate: { lo: 8.2, hi: 9.2, minControl: 8.2, fastCarbon: 10.1 },
  advanced: { lo: 8.8, hi: 10, minControl: 0, fastCarbon: 10.1 },
};
// Style is the stiffness side: flexible blades hold the ball longer (spin), stiff ones give drives and hits.
const STYLE_STIFFNESS: Record<BladeStyle, { lo: number; hi: number }> = { spin: { lo: 0, hi: 5.8 }, speed: { lo: 4.8, hi: 10 } };
// Feel is how speed compares with control; "balanced" is a band around equal.
const FEEL_GAP: Record<Exclude<Feel, "any">, (gap: number) => boolean> = {
  control: (gap) => gap <= -0.4,
  balanced: (gap) => Math.abs(gap) < 0.4,
  speed: (gap) => gap >= 0.4,
};
const MIN_OVERALL = 8.0;

/** 0 for (allowance-20, allowance], 1 for (allowance-40, allowance-20], ... Pricier blades are usually better, so band 0 ranks first. */
export const band = (price: number, allowance: number) => Math.floor((allowance - price) / BAND + 1e-9);

const BLADES = (data as Omit<Blade, "buyLinks">[]).map((b) => ({ ...b, buyLinks: bladeBuyLinks(b.name) })) as Blade[];

export const allBlades = () => BLADES;
export const bladeBySlug = (slug: string) => BLADES.find((b) => b.slug === slug);

// Fibre words in a blade's name; used only when no page stated the layers, and always shown as "from the name".
const NAME_FIBRE = /\b(?:alc|zlc|zlf|carbon|carbonado|kevlar|zylon|innerforce|outerforce|inner force|aryl\w*)\b/i;
export function layers(b: Pick<Blade, "name" | "composition">): Layers {
  if (b.composition) return { composite: b.composition !== "wood", inferred: false };
  return NAME_FIBRE.test(b.name) ? { composite: true, inferred: true } : { composite: null, inferred: false };
}

/** The handle filters a blade can be matched on: only values at least one blade has, so none is offered empty. */
export function handleFilters(): HandleFilter[] {
  const have = new Set(BLADES.flatMap((b) => b.handles));
  return HANDLE_FILTERS.filter((h) => h === "any" || (h === "penhold" ? have.has("CS") || have.has("JP") || have.has("PH") : have.has(h)));
}
export const hasHandle = (b: Blade, f: HandleFilter) =>
  f === "any" || (f === "penhold" ? b.handles.some((h) => h === "CS" || h === "JP" || h === "PH") : b.handles.includes(f));

/** The matching rubber: the same style and level as the blade search, and the budget left after the blade. */
export function combo(blade: Blade, style: BladeStyle, level: BladeLevel, budget: number): Combo {
  const left = Math.max(0, Math.floor(budget - blade.price));
  const [rubber] = left > 0 ? recommendRubbers(style, "inverted", level, left, 1).results : [];
  return { budget: left, rubber: rubber ?? null };
}

/** Drop blades over budget, then rank by budget band (closest first) and the highest user score (Overall). */
export function recommend(style: BladeStyle, level: BladeLevel, budget = DEFAULT_BUDGET, handle: HandleFilter = "any", feel: Feel = "any", limit = 8): BladeRecommendation {
  const rule = LEVEL_RULES[level];
  const flex = STYLE_STIFFNESS[style];
  const allowance = bladeAllowance(budget);
  const fits = BLADES.filter((b) => {
    if (b.price > allowance || b.overall < MIN_OVERALL) return false;
    if (b.speed < rule.lo || b.speed > rule.hi || b.control < rule.minControl) return false;
    if (b.stiffness < flex.lo || b.stiffness > flex.hi) return false;
    if (feel !== "any" && !FEEL_GAP[feel](b.speed - b.control)) return false;
    return !(layers(b).composite && b.speed >= rule.fastCarbon);
  });
  const picks = fits.filter((b) => hasHandle(b, handle));
  const stylePull = (b: Blade) => (style === "spin" ? b.stiffness : -b.speed);
  picks.sort((a, b) => band(a.price, allowance) - band(b.price, allowance) || b.overall - a.overall || stylePull(a) - stylePull(b));
  return {
    style, level, budget, handle, feel,
    results: picks.slice(0, limit).map((b) => ({ ...b, ...layers(b), combo: combo(b, style, level, budget) })),
    noHandleInfo: handle === "any" ? 0 : fits.filter((b) => b.handles.length === 0).length,
  };
}
