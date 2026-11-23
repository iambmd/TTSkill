"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Level, Recommendation, Rubber, Style } from "@/lib/rubbers";
import { RubberBuyMenu } from "./rubber-buy-menu";

const DEFAULT_BUDGET = 60;
const BUDGETS = [
  { value: 40, label: "$40" },
  { value: DEFAULT_BUDGET, label: "$60" },
  { value: 80, label: "$80" },
  { value: 500, label: "$100+" },
];

export function GearQuiz() {
  const [style, setStyle] = useState<Style>();
  const [level, setLevel] = useState<Level>();
  const [budget, setBudget] = useState(DEFAULT_BUDGET);
  const [result, setResult] = useState<{ query: string; pick?: Rubber; error?: boolean }>();
  const query = style && level ? new URLSearchParams({ style, level, budget: String(budget) }).toString() : "";
  const current = result?.query === query ? result : undefined;
  const pick = current?.pick;

  useEffect(() => {
    if (!query) return;
    const request = new AbortController();
    fetch(`/api/rubbers?${query}&rubber_type=inverted&demo=1`, { signal: request.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Couldn't load rubbers.");
        const { results }: Recommendation = await response.json();
        if (!request.signal.aborted) setResult({ query, pick: results[0] });
      })
      .catch(() => {
        if (!request.signal.aborted) setResult({ query, error: true });
      });
    return () => request.abort();
  }, [query]);

  return (
    <section aria-labelledby="home-quiz-title" className="home-quiz surface-card">
      <div className="home-quiz-controls">
        <h3 id="home-quiz-title" className="section-title text-xl">Find your rubber</h3>
        <fieldset className="home-quiz-options">
          <legend>Play style</legend>
          {(["spin", "speed"] as const).map((value) => (
            <button key={value} type="button" aria-pressed={style === value} onClick={() => setStyle(value)}>{value}</button>
          ))}
        </fieldset>
        <fieldset className="home-quiz-options">
          <legend>Level</legend>
          {(["beginner", "intermediate", "advanced"] as const).map((value) => (
            <button key={value} type="button" aria-pressed={level === value} onClick={() => setLevel(value)}>{value}</button>
          ))}
        </fieldset>
        <fieldset className="home-quiz-options">
          <legend>Budget per sheet</legend>
          {BUDGETS.map(({ value, label }) => (
            <button key={value} type="button" aria-pressed={budget === value} onClick={() => setBudget(value)}>{label}</button>
          ))}
        </fieldset>
      </div>
      {query && (
        <div className="home-quiz-result">
          <div className="min-w-0 space-y-2">
            <p role="status">
              {pick ? <>Your pick <strong className="text-accent">{pick.name}</strong>{pick.price !== null && <> · <span className="tabular-nums">${pick.price.toFixed(2)}</span></>}</>
                : !current ? "Finding your rubber…"
                : current.error ? "Couldn't load your pick. Try Rubber Finder."
                : `Nothing under $${budget} yet. Try a higher budget.`}
            </p>
            {pick && <RubberBuyMenu product={pick.name} buyLinks={pick.buyLinks} buyLink={pick.buyLink} buyUrl={pick.buyUrl} />}
          </div>
          <Link href={`/rubbers?${query}`} prefetch={false} className="home-text-link">Open Rubber Finder</Link>
        </div>
      )}
    </section>
  );
}
