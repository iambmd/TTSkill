"use client";

import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { usd } from "@/lib/format";
import type { Level, Recommendation, Rubber, Style } from "@/lib/rubbers";
import { BuyMenu } from "./buy-menu";

const DEFAULT_BUDGET = 60;
// 500 is the finder's ceiling, shown as "$100+".
const BUDGETS = [{ value: 40 }, { value: DEFAULT_BUDGET }, { value: 80 }, { value: 500, label: 100 }];

export function GearQuiz() {
  const t = useTranslations("home.quiz");
  const tr = useTranslations("rubbers");
  const format = useFormatter();
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
        if (!response.ok) throw new Error(String(response.status));   // shown as t("failed")
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
        <h3 id="home-quiz-title" className="section-title text-xl">{t("title")}</h3>
        <fieldset className="home-quiz-options">
          <legend>{t("playStyle")}</legend>
          {(["spin", "speed"] as const).map((value) => (
            <button key={value} type="button" aria-pressed={style === value} onClick={() => setStyle(value)}>{tr(`styles.${value}`)}</button>
          ))}
        </fieldset>
        <fieldset className="home-quiz-options">
          <legend>{t("level")}</legend>
          {(["beginner", "intermediate", "advanced"] as const).map((value) => (
            <button key={value} type="button" aria-pressed={level === value} onClick={() => setLevel(value)}>{tr(`levels.${value}`)}</button>
          ))}
        </fieldset>
        <fieldset className="home-quiz-options">
          <legend>{t("budget")}</legend>
          {BUDGETS.map(({ value, label }) => (
            <button key={value} type="button" aria-pressed={budget === value} onClick={() => setBudget(value)}>{label ? `${usd(format, label, true)}+` : usd(format, value, true)}</button>
          ))}
        </fieldset>
      </div>
      {query && (
        <div className="home-quiz-result">
          <div className="min-w-0 space-y-2">
            <p role="status">
              {pick ? <>{t("yourPick")} <strong className="text-accent">{pick.name}</strong>{pick.price !== null && <> · <span className="tabular-nums">{usd(format, pick.price)}</span></>}</>
                : !current ? t("finding")
                : current.error ? t("failed")
                : t("nothing", { budget: usd(format, budget, true) })}
            </p>
            {pick && <BuyMenu product={pick.name} buyLinks={pick.buyLinks} buyLink={pick.buyLink} buyUrl={pick.buyUrl} />}
          </div>
          <Link href={`/rubbers?${query}`} prefetch={false} className="home-text-link">{t("open")}</Link>
        </div>
      )}
    </section>
  );
}
