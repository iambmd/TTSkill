/** Blade finder types and constants with no data in them, so client components can import them without the dataset. */
import type { Level, Rubber, Style } from "./rubbers";
import type { BuyLinkData } from "./buy-links";

export const STYLES = ["spin", "speed"] as const;
export const LEVELS = ["beginner", "intermediate", "advanced"] as const;
export const FEELS = ["any", "control", "balanced", "speed"] as const;
export const HANDLE_FILTERS = ["any", "FL", "ST", "AN", "penhold"] as const;
export type BladeStyle = Style;
export type BladeLevel = Level;
export type Feel = (typeof FEELS)[number];
export type HandleFilter = (typeof HANDLE_FILTERS)[number];
export type Handle = "FL" | "ST" | "AN" | "CS" | "JP" | "PH"; // PH: a penhold handle the store did not say is Chinese or Japanese
export type Composition = "wood" | "inner" | "outer" | "composite";

export type Blade = BuyLinkData & {
  slug: string; name: string; brand: string; price: number;
  speed: number; control: number; stiffness: number; hardness: number | null; overall: number; ratings: number; url: string;
  plies: number | null; weight: number | null; composition: Composition | null; fiber: string | null;
  handles: Handle[]; specSources: string[];
};
/** Carbon or fibre layers: what the data says, or what the name says (flagged, never stored). */
export type Layers = { composite: boolean | null; inferred: boolean };
export type Combo = { budget: number; rubber: Rubber | null };
export type BladeResult = Blade & Layers & { combo: Combo };
export type BladeRecommendation = {
  style: BladeStyle; level: BladeLevel; budget: number; handle: HandleFilter; feel: Feel;
  results: BladeResult[]; noHandleInfo: number;
};

export const BAND = 20;           // blades cost more than rubbers, so budget steps are $20
export const RUBBER_RESERVE = 20; // the budget covers the blade and one rubber, so a blade always leaves at least this much
export const BLADE_SHARE = 0.6;   // about this share of the budget is planned for the blade, the rest for the rubber
export const DEFAULT_BUDGET = 150;

/** What the blade may cost: its share of the budget, never leaving less than RUBBER_RESERVE for the rubber.
 * Ranking starts from here, so the best-ranked blades leave real money for the rubber that goes with them. */
export const bladeAllowance = (budget: number) => Math.max(0, Math.min(budget - RUBBER_RESERVE, Math.round(budget * BLADE_SHARE)));

// Plain-word tiers for the short summary line; the words themselves live in messages/*.json (blades.paces ...).
export const paceTier = (speed: number) => (speed < 8.0 ? "slow" : speed < 8.8 ? "medium" : speed < 9.3 ? "fast" : "veryFast") as "slow" | "medium" | "fast" | "veryFast";
export const controlTier = (control: number) => (control >= 9.2 ? "high" : control >= 8.5 ? "good" : "fair") as "high" | "good" | "fair";
export const flexTier = (stiffness: number) => (stiffness < 4.0 ? "flexible" : stiffness <= 6.5 ? "medium" : "stiff") as "flexible" | "medium" | "stiff";
