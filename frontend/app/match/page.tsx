"use client";

import demoAssets from "@/lib/demo-assets.json";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { submitJob } from "@/lib/submit";
import { feetInches, heightProblem, LIMITS } from "@/lib/validate";
import { FieldError, PageIntro, RadioTiles, SubmitBar, inputClass, labelClass } from "../ui";
import { ExampleSection } from "../examples";
import { VideoPicker } from "../video-picker";

const STROKES = ["forehand", "backhand"] as const;
const HANDS = ["auto", "right", "left"] as const;
const GRIPS = ["shakehand", "penhold"] as const;
const UNITS = ["cm", "ft"] as const;
const STEPS = ["one", "two", "three", "four", "five"] as const;

const unitTag = (u: string) => (
  <span className="pointer-events-none absolute top-1/2 right-4 -translate-y-1/2 text-sm font-semibold text-muted">{u}</span>
);

export default function MatchPage() {
  const t = useTranslations("match");
  const tAll = useTranslations();
  const locale = useLocale();
  const tv = useTranslations("validation");
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [starting, setStarting] = useState(tAll("common.starting"));
  const [videoProblem, setVideoProblem] = useState<string | null>(null);
  const [unit, setUnit] = useState<"cm" | "ft">("cm");
  const [cm, setCm] = useState("");
  const [ft, setFt] = useState("");
  const [inch, setInch] = useState("");

  const imperial = feetInches(ft, inch, tv);
  const heightError = unit === "cm" ? heightProblem(cm, tv) : imperial.error;
  const heightCm = unit === "cm" ? (cm.trim() ? cm.trim() : null) : imperial.cm !== null ? String(imperial.cm) : null;

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (videoProblem || heightError) return;
    const form = new FormData(e.currentTarget);
    const video = form.get("video") as File | null;
    const url = String(form.get("url") ?? "").trim();
    const hasVideo = !!video && video.size > 0;
    if (!hasVideo && !url) {
      setError(tv("matchVideo"));
      return;
    }
    if (!hasVideo) form.delete("video");
    if (hasVideo || !url) form.delete("url");
    if (heightCm) form.set("height_cm", heightCm);
    else form.delete("height_cm");
    setStarting(form.has("url") ? tAll("common.checkingLink") : tAll("common.starting"));
    setProgress(0);
    setError(null);
    try {
      const job = await submitJob("match", form, setProgress, tAll);
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError((err as Error).message);
      setProgress(null);
    }
  }

  return (
    <>
    <form onSubmit={onSubmit} noValidate className="feature-form">
      <PageIntro
        eyebrow={t("eyebrow")}
        title={t("title")}
        body={t("body")}
      />
      {/* The pros' differences, warnings and title cards come back in the page's language. */}
      <input type="hidden" name="lang" value={locale} />
      <VideoPicker findPlayer
        kind="match" onProblem={setVideoProblem}
        title={t("videoTitle")} hint={t("videoHint")}
      />
      <div className="min-w-0 space-y-6">
        <fieldset>
          <legend className={labelClass}>{t("stroke")}</legend>
          <RadioTiles name="stroke" options={STROKES.map((value) => ({ value, label: tAll(`strokes.${value}`) }))} defaultValue="forehand" className="grid-cols-2" />
        </fieldset>
        <fieldset>
          <legend className={labelClass}>{t("grip")}</legend>
          <RadioTiles name="grip" options={GRIPS.map((value) => ({ value, label: tAll(`grips.${value}`), sub: tAll(`grips.${value}Sub`) }))} defaultValue="shakehand" className="grid-cols-2" />
          <p className="mt-2 text-xs text-muted">{t("gripHint")}</p>
        </fieldset>
        <div>
          <div className="mb-2 flex items-center justify-between gap-3">
            <label className={`${labelClass} mb-0`} htmlFor={unit === "cm" ? "height_cm" : "height_ft"}>
              {t("height")} <span className="font-medium tracking-normal normal-case text-muted">{tAll("common.optional")}</span>
            </label>
            <div role="radiogroup" aria-label={t("heightUnit")} className="flex rounded-lg border border-line p-0.5 text-xs font-bold">
              {UNITS.map((u) => (
                <button
                  key={u} type="button" role="radio" aria-checked={unit === u} onClick={() => setUnit(u)}
                  className={`h-9 rounded-md px-3 ${unit === u ? "action-fill" : "text-muted hover:text-white"}`}
                >
                  {t(`units.${u}`)}
                </button>
              ))}
            </div>
          </div>
          {unit === "cm" ? (
            <div className="relative">
              <input
                id="height_cm" type="text" inputMode="decimal" autoComplete="off" value={cm} onChange={(e) => setCm(e.target.value)}
                placeholder={t("cmPlaceholder")} aria-invalid={!!heightError} aria-describedby="height-error"
                className={`${inputClass} pr-14 ${heightError ? "border-red-500/50" : ""}`}
              />
              {unitTag(t("units.cm"))}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <div className="relative">
                <input
                  id="height_ft" type="text" inputMode="numeric" autoComplete="off" value={ft} onChange={(e) => setFt(e.target.value)}
                  placeholder="5" aria-label={t("feet")} aria-invalid={!!heightError} aria-describedby="height-error"
                  className={`${inputClass} pr-12 ${heightError ? "border-red-500/50" : ""}`}
                />
                {unitTag(t("units.feet"))}
              </div>
              <div className="relative">
                <input
                  type="text" inputMode="decimal" autoComplete="off" value={inch} onChange={(e) => setInch(e.target.value)}
                  placeholder="10" aria-label={t("inches")} aria-invalid={!!heightError} aria-describedby="height-error"
                  className={`${inputClass} pr-12 ${heightError ? "border-red-500/50" : ""}`}
                />
                {unitTag(t("units.inches"))}
              </div>
            </div>
          )}
          <FieldError id="height-error">{heightError}</FieldError>
          {!heightError && (
            <p className="mt-2 text-xs text-muted">
              {t("heightHint", { min: LIMITS.height_cm.min, max: LIMITS.height_cm.max })}
            </p>
          )}
        </div>
        <fieldset>
          <legend className={labelClass}>{t("hand")}</legend>
          <RadioTiles name="hand" options={HANDS.map((value) => ({ value, label: tAll(`hands.${value}`) }))} defaultValue="auto" className="grid-cols-3" />
        </fieldset>
      </div>
      <SubmitBar
        label={t("submit")} progress={progress} error={error} startingLabel={starting}
        blocked={!!videoProblem || !!heightError}
      />
    </form>
      <ExampleSection
        before={{ src: "/examples/match-before.mp4", label: tAll("common.before"), caption: t("beforeCaption") }}
        after={{ src: demoAssets.match.url, label: tAll("common.after"), caption: tAll("demoDescriptions.match"), vertical: true }}
        steps={STEPS.map((s) => t(`steps.${s}`))}
      />
    </>
  );
}
