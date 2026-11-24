import { DEFAULT_BUDGET, FEELS, HANDLE_FILTERS, LEVELS, STYLES, handleFilters } from "@/lib/blades";
import { BladeFinder } from "./blade-finder";

export default async function BladesPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  const style = STYLES.find((option) => option === params.style) ?? "spin";
  const level = LEVELS.find((option) => option === params.level) ?? "intermediate";
  const handle = HANDLE_FILTERS.find((option) => option === params.handle) ?? "any";
  const feel = FEELS.find((option) => option === params.feel) ?? "any";
  const budget = typeof params.budget === "string" ? Number(params.budget) : NaN;
  const initialBudget = budget >= 1 && budget <= 500 ? budget : DEFAULT_BUDGET;
  const handles = handleFilters(); // only the handles at least one blade is known to come with
  return (
    <BladeFinder
      key={`${style}-${level}-${initialBudget}-${handle}-${feel}`}
      initial={{ style, level, budget: initialBudget, handle: handles.includes(handle) ? handle : "any", feel }}
      handles={handles}
    />
  );
}
