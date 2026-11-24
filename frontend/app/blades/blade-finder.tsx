"use client";

import { useFormatter, useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { usd, usdSymbol } from "@/lib/format";
import {
  BAND, BLADE_SHARE, FEELS, LEVELS, RUBBER_RESERVE, STYLES,
  type BladeLevel, type BladeRecommendation, type BladeStyle, type Feel, type HandleFilter,
} from "@/lib/blade-types";
import { AffiliateDisclosure } from "../buy-menu";
import { GearTabs } from "../gear-tabs";
import { PageIntro, RadioTiles, inputClass, labelClass } from "../ui";
import { BladeCard } from "./blade-card";

export function BladeFinder({ initial, handles }: {
  initial: { style: BladeStyle; level: BladeLevel; budget: number; handle: HandleFilter; feel: Feel };
  handles: HandleFilter[];
}) {
  const t = useTranslations("blades");
  const tAll = useTranslations();
  const format = useFormatter();
  const locale = useLocale();
  const symbol = usdSymbol(locale);
  const [style, setStyle] = useState<BladeStyle>(initial.style);
  const [level, setLevel] = useState<BladeLevel>(initial.level);
  const [handle, setHandle] = useState<HandleFilter>(initial.handle);
  const [feel, setFeel] = useState<Feel>(initial.feel);
  const [budget, setBudget] = useState(String(initial.budget));
  const [rec, setRec] = useState<BladeRecommendation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const n = Number(budget);
    if (!(n > 0 && n <= 500)) {
      setError(tAll("errors.budget", { min: usd(format, 1, true), max: usd(format, 500, true) }));
      return;
    }
    const params = new URLSearchParams({ style, level, budget: String(n), handle, feel });
    fetch(`/api/blades?${params}`)
      .then(async (r) => {
        const body = await r.json();
        if (!r.ok) throw new Error(body.error ?? t("loadFailed"));
        if (live) { setRec(body); setError(null); }
      })
      .catch((e: Error) => live && setError(e.message));
    return () => { live = false; };
  }, [style, level, budget, handle, feel]);   // eslint-disable-line react-hooks/exhaustive-deps -- t, format only label errors

  return (
    <div className="space-y-7">
      <GearTabs active="blades" />
      <PageIntro eyebrow={t("eyebrow")} title={t("title")} body={t("body")} />
      <div className="grid gap-6 md:grid-cols-2 md:items-start md:gap-8">
        <div className="min-w-0 space-y-6">
          <fieldset>
            <legend className={labelClass}>{t("style")}</legend>
            <RadioTiles name="style" options={STYLES.map((value) => ({ value, label: t(`styles.${value}`), sub: t(`styles.${value}Sub`) }))} value={style} onChange={setStyle} className="grid-cols-2" />
          </fieldset>
          <fieldset>
            <legend className={labelClass}>{t("level")}</legend>
            <RadioTiles name="level" options={LEVELS.map((value) => ({ value, label: t(`levels.${value}`) }))} value={level} onChange={setLevel} className="grid-cols-3" />
          </fieldset>
          <fieldset>
            <legend className={labelClass}>{t("feel")}</legend>
            <RadioTiles name="feel" options={FEELS.map((value) => ({ value, label: t(`feels.${value}`) }))} value={feel} onChange={setFeel} className="grid-cols-2" />
          </fieldset>
          <fieldset>
            <legend className={labelClass}>{t("handle")}</legend>
            <RadioTiles name="handle" options={handles.map((value) => ({ value, label: t(`handles.${value}`) }))} value={handle} onChange={setHandle} className="grid-cols-2" />
            <p className="mt-2 text-xs text-muted">{t("handleHint")}</p>
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
            <p className="mt-2 text-xs text-muted">{t("budgetHint", { share: format.number(BLADE_SHARE, { style: "percent" }), reserve: usd(format, RUBBER_RESERVE, true), step: usd(format, BAND, true) })}</p>
          </div>
        </div>
        <section aria-live="polite" className="min-w-0 space-y-3">
          {error && <p role="alert" className="rounded-2xl border border-red-500/40 bg-red-500/10 p-4 text-sm">{error}</p>}
          {rec && !error && (
            <>
              {rec.results.length === 0 && <p className="surface-card p-4 text-sm text-muted">{t("nothing")}</p>}
              {rec.noHandleInfo > 0 && <p className="text-xs text-muted">{t("noHandleInfo", { n: rec.noHandleInfo })}</p>}
              <ol className="space-y-2">
                {rec.results.map((blade, i) => <BladeCard key={blade.slug} blade={blade} rank={i + 1} combo={blade.combo} />)}
              </ol>
              <p className="text-xs text-muted">{t("note")}</p>
              {rec.results.length > 0 && <AffiliateDisclosure />}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
