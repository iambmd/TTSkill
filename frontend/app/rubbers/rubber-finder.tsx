"use client";

import { useFormatter, useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { rating, usd, usdSymbol } from "@/lib/format";
import { THICKNESS, type Level, type Recommendation, type RubberType, type Style } from "@/lib/rubbers";
import { GearTabs } from "../gear-tabs";
import { RubberBuyMenu } from "../rubber-buy-menu";
import { PageIntro, RadioTiles, inputClass, labelClass } from "../ui";

const STYLES = ["spin", "speed"] as const;
const TYPES = ["inverted", "short_pips", "long_pips", "anti_spin"] as const;
const LEVELS = ["beginner", "intermediate", "advanced"] as const;
const PIPS_NOTE = "PingSense has no pips rubbers yet, so there is nothing to rank. They're on the list.";

type T = ReturnType<typeof useTranslations>;
type F = ReturnType<typeof useFormatter>;

/** The recommender's sponge thickness ("1.8-2.0 mm", "2.1 mm or max") in the page's language.
 * Only the known English phrases are rewritten; anything else is shown as sent. */
export function thicknessText(raw: string, t: T, format: F) {
  const n = (s: string) => format.number(Number(s), { maximumFractionDigits: 1, minimumFractionDigits: s.includes(".") ? 1 : 0 });
  let m;
  if ((m = /^([\d.]+) mm or max$/.exec(raw))) return t("thicknesses.maxOr", { mm: `${n(m[1])} mm` });
  if ((m = /^([\d.]+)-([\d.]+) mm$/.exec(raw))) return t("thicknesses.range", { from: n(m[1]), to: n(m[2]) });
  if ((m = /^OX \(no sponge\) to ([\d.]+) mm$/.exec(raw))) return t("thicknesses.ox", { to: n(m[1]) });
  return raw;
}

export function RubberFinder({ initialStyle, initialLevel, initialBudget, demo }: {
  initialStyle: Style; initialLevel: Level; initialBudget: number; demo: boolean;
}) {
  const t = useTranslations("rubbers");
  const tAll = useTranslations();
  const format = useFormatter();
  const locale = useLocale();
  const symbol = usdSymbol(locale);
  const fmt = (v: number | null) => (v === null ? t("tbd") : rating(format, v));
  const [style, setStyle] = useState<Style>(initialStyle);
  const [type, setType] = useState<RubberType>("inverted");
  const [level, setLevel] = useState<Level>(initialLevel);
  const [budget, setBudget] = useState(String(initialBudget));
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const n = Number(budget);
    if (!(n > 0 && n <= 500)) {
      setError(tAll("errors.budget", { min: usd(format, 1, true), max: usd(format, 500, true) }));
      return;
    }
    const params = new URLSearchParams({ style, rubber_type: type, level, budget: String(n) });
    if (demo) params.set("demo", "1");
    fetch(`/api/rubbers?${params}`)
      .then(async (r) => {
        const body = await r.json();
        if (!r.ok) throw new Error(body.error ?? t("loadFailed"));
        if (live) { setRec(body); setError(null); }
      })
      .catch((e: Error) => live && setError(e.message));
    return () => { live = false; };
  }, [style, type, level, budget, demo]);   // eslint-disable-line react-hooks/exhaustive-deps -- t, format only label errors

  return (
    <div className="space-y-7">
      <GearTabs active="rubbers" />
      <PageIntro
        eyebrow={t("eyebrow")}
        title={t("title")}
        body={t("body")}
      />
      <div className="grid gap-6 md:grid-cols-2 md:items-start md:gap-8">
        <div className="min-w-0 space-y-6">
          <fieldset>
            <legend className={labelClass}>{t("style")}</legend>
            <RadioTiles name="style" options={STYLES.map((value) => ({ value, label: t(`styles.${value}`), sub: t(`styles.${value}Sub`) }))} value={style} onChange={setStyle} className="grid-cols-2" />
          </fieldset>
          <fieldset>
            <legend className={labelClass}>{t("type")}</legend>
            <RadioTiles name="type" options={TYPES.map((value) => ({ value, label: t(`types.${value}`) }))} value={type} onChange={setType} className="grid-cols-2" />
          </fieldset>
          <fieldset>
            <legend className={labelClass}>{t("level")}</legend>
            <RadioTiles name="level" options={LEVELS.map((value) => ({ value, label: t(`levels.${value}`) }))} value={level} onChange={setLevel} className="grid-cols-3" />
          </fieldset>

          <div>
            <label className={labelClass} htmlFor="budget">{t("budget")}</label>
            <div className="relative">
              <span className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-sm font-semibold text-muted">{symbol}</span>
              <input
                id="budget" type="number" inputMode="numeric" min={1} max={500} step={1} value={budget}
                onChange={(e) => setBudget(e.target.value)} className={`${inputClass} h-12 ${symbol.length > 1 ? "pl-14" : "pl-8"}`}
              />
            </div>
            <p className="mt-2 text-xs text-muted">{t("budgetHint", { step: usd(format, 10, true) })}</p>
          </div>
        </div>
        <section aria-live="polite" className="min-w-0 space-y-3">
          {error && <p role="alert" className="rounded-2xl border border-red-500/40 bg-red-500/10 p-4 text-sm">{error}</p>}
          {rec && !error && (
            <>
              <div className="surface-card flex flex-wrap items-baseline justify-between gap-2 border-s-[4px] border-s-accent p-4">
                <span className="text-sm font-semibold text-muted">{t("thickness")}</span>
                <span className="stat text-xl text-accent">{rec.thickness === THICKNESS[type][level] ? thicknessText(rec.thickness, t, format) : rec.thickness}</span>
              </div>
              {rec.note && <p className="surface-card p-4 text-sm text-muted">{rec.note === PIPS_NOTE ? t("pipsNote") : rec.note}</p>}
              {!rec.note && rec.results.length === 0 && (
                <p className="surface-card p-4 text-sm text-muted">{t("nothing")}</p>
              )}
              <ol className="space-y-2">
                {rec.results.map((r, i) => (
                  <li key={r.name} className="surface-card space-y-3 p-4">
                    <div className="flex items-center gap-4">
                      <span className="stat w-6 shrink-0 text-xl text-accent">{i + 1}</span>
                      <div className="min-w-0 flex-1">
                        <p className="break-words font-bold">{r.name}</p>
                        <p className="text-xs text-muted">
                          {t("ratings", { speed: fmt(r.speed), spin: fmt(r.spin), control: fmt(r.control) })}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="stat text-xl">{r.price !== null && usd(format, r.price, true)}</p>
                        <p className="text-xs text-muted">{t("score", { score: fmt(r.overall) })}</p>
                      </div>
                    </div>
                    <RubberBuyMenu product={r.name} buyLinks={r.buyLinks} buyLink={r.buyLink} buyUrl={r.buyUrl} />
                  </li>
                ))}
              </ol>
              <p className="text-xs text-muted">
                {t("source")}
              </p>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
