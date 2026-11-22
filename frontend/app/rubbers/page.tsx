"use client";

import { useEffect, useState } from "react";
import type { Level, Recommendation, RubberType, Style } from "@/lib/rubbers";
import { GearTabs } from "../gear-tabs";
import { RubberBuyMenu } from "../rubber-buy-menu";
import { PageIntro, RadioTiles, inputClass, labelClass } from "../ui";

const STYLE_OPTIONS = [
  { value: "spin", label: "Spin", sub: "Loops and heavy topspin" },
  { value: "speed", label: "Speed", sub: "Drives and fast hits" },
] as const;
const TYPE_OPTIONS = [
  { value: "inverted", label: "Inverted" },
  { value: "short_pips", label: "Short pips" },
  { value: "long_pips", label: "Long pips" },
  { value: "anti_spin", label: "Anti-spin" },
] as const;
const LEVEL_OPTIONS = [
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
] as const;

const fmt = (v: number | null) => (v === null ? "TBD" : v.toFixed(1));

export default function RubbersPage() {
  const [style, setStyle] = useState<Style>("spin");
  const [type, setType] = useState<RubberType>("inverted");
  const [level, setLevel] = useState<Level>("intermediate");
  const [budget, setBudget] = useState("60");
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const n = Number(budget);
    if (!(n > 0 && n <= 500)) {
      setError("Enter a budget between $1 and $500.");
      return;
    }
    fetch(`/api/rubbers?${new URLSearchParams({ style, rubber_type: type, level, budget: String(n) })}`)
      .then(async (r) => {
        const body = await r.json();
        if (!r.ok) throw new Error(body.error ?? "Couldn't load rubbers. Try again.");
        if (live) { setRec(body); setError(null); }
      })
      .catch((e: Error) => live && setError(e.message));
    return () => { live = false; };
  }, [style, type, level, budget]);

  return (
    <div className="space-y-7">
      <GearTabs active="rubbers" />
      <PageIntro
        eyebrow="Rubber finder"
        title="Pick your rubber"
        body="Tell us how you play and what you can spend. Pricier rubbers are usually better, so we start near your budget and rank by what players who use them think."
      />
      <div className="grid gap-6 md:grid-cols-2 md:items-start md:gap-8">
        <div className="min-w-0 space-y-6">
          <fieldset>
            <legend className={labelClass}>Style</legend>
            <RadioTiles name="style" options={STYLE_OPTIONS} value={style} onChange={setStyle} className="grid-cols-2" />
          </fieldset>
          <fieldset>
            <legend className={labelClass}>Rubber type</legend>
            <RadioTiles name="type" options={TYPE_OPTIONS} value={type} onChange={setType} className="grid-cols-2" />
          </fieldset>
          <fieldset>
            <legend className={labelClass}>Level</legend>
            <RadioTiles name="level" options={LEVEL_OPTIONS} value={level} onChange={setLevel} className="grid-cols-3" />
          </fieldset>

          <div>
            <label className={labelClass} htmlFor="budget">Budget per sheet</label>
            <div className="relative">
              <span className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-sm font-semibold text-muted">$</span>
              <input
                id="budget" type="number" inputMode="numeric" min={1} max={500} step={1} value={budget}
                onChange={(e) => setBudget(e.target.value)} className={`${inputClass} h-12 pl-8`}
              />
            </div>
            <p className="mt-2 text-xs text-muted">Nothing over budget. We rank in $10 steps down from it, best rated first in each step.</p>
          </div>
        </div>
        <section aria-live="polite" className="min-w-0 space-y-3">
          {error && <p role="alert" className="rounded-2xl border border-red-500/40 bg-red-500/10 p-4 text-sm">{error}</p>}
          {rec && !error && (
            <>
              <div className="surface-card flex flex-wrap items-baseline justify-between gap-2 border-s-[4px] border-s-accent p-4">
                <span className="text-sm font-semibold text-muted">Sponge thickness</span>
                <span className="text-xl font-bold text-accent">{rec.thickness}</span>
              </div>
              {rec.note && <p className="surface-card p-4 text-sm text-muted">{rec.note}</p>}
              {!rec.note && rec.results.length === 0 && (
                <p className="surface-card p-4 text-sm text-muted">Nothing matches yet. Try another level.</p>
              )}
              <ol className="space-y-2">
                {rec.results.map((r, i) => (
                  <li key={r.name} className="surface-card space-y-3 p-4">
                    <div className="flex items-center gap-4">
                      <span className="w-6 shrink-0 text-xl font-bold tabular-nums text-accent">{i + 1}</span>
                      <div className="min-w-0 flex-1">
                        <p className="break-words font-bold">{r.name}</p>
                        <p className="text-xs text-muted">
                          Speed {fmt(r.speed)} · Spin {fmt(r.spin)} · Control {fmt(r.control)}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-xl font-bold tabular-nums">${r.price?.toFixed(0)}</p>
                        <p className="text-xs text-muted">score {fmt(r.overall)}</p>
                      </div>
                    </div>
                    <RubberBuyMenu product={r.name} buyLinks={r.buyLinks} buyLink={r.buyLink} buyUrl={r.buyUrl} />
                  </li>
                ))}
              </ol>
              <p className="text-xs text-muted">
                Ratings and prices: revspin.net user reviews, via PingSense. Scores are out of 10.
              </p>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
