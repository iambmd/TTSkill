"use client";

import demoAssets from "@/lib/demo-assets.json";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useRef, useState } from "react";
import { submitJob, type RallyClip } from "@/lib/submit";
import { STROKE_TYPES } from "@/lib/strokes";
import { LIMITS, textProblem } from "@/lib/validate";
import { ChevronIcon, FieldError, PageIntro, RadioTiles, SubmitBar, inputClass, labelClass } from "../ui";
import { ExampleSection } from "../examples";
import { VideoPicker } from "../video-picker";
import { MatchSource } from "../match-source";

const HANDS = ["auto", "right", "left"] as const;
const STEPS = ["one", "two", "three", "four", "five"] as const;

export default function BreakdownForm({ sourceJob, rallyId, clip }: { sourceJob?: string; rallyId?: string; clip?: RallyClip }) {
  const t = useTranslations("breakdown");
  const tAll = useTranslations();
  const tv = useTranslations("validation");
  const te = useTranslations("errors");
  const locale = useLocale();
  const router = useRouter();
  const textRef = useRef<HTMLDetailsElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [starting, setStarting] = useState(tAll("common.starting"));
  const [videoProblem, setVideoProblem] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const notesError = textProblem(notes, "training_text", tv("labels.description"), tv);
  const blocked = !!videoProblem || !!notesError;

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (blocked) return;
    const form = new FormData(e.currentTarget);
    const video = form.get("video") as File | null;
    const url = String(form.get("url") ?? "").trim();
    const text = String(form.get("text") ?? "").trim();
    const hasVideo = !!video && video.size > 0;
    if (!hasVideo && !url && !sourceJob && !text) {
      setError(t("needInput"));
      if (textRef.current) textRef.current.open = true;
      return;
    }
    if (!hasVideo) form.delete("video");
    if (hasVideo || !url) form.delete("url");
    setStarting(form.has("url") ? tAll("common.checkingLink") : tAll("common.starting"));
    setProgress(0);
    setError(null);
    try {
      const job = await submitJob("breakdown", form, setProgress, te);
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
      {/* The step cards, drill and video text are written in the page's language. */}
      <input type="hidden" name="lang" value={locale} />
      {sourceJob ? <MatchSource job={sourceJob} rallyId={rallyId} clip={clip} form="breakdown" /> : (
        <VideoPicker findPlayer onlyMeOption
          kind="breakdown" onProblem={setVideoProblem}
          title={t("videoTitle")} hint={t("videoHint")}
        />
      )}
      <div className="min-w-0 space-y-6">
        <details ref={textRef} className="group surface-card">
          <summary className="flex list-none items-center justify-between px-4 py-3.5 text-sm font-semibold [&::-webkit-details-marker]:hidden">
            {t("describe")}
            <span aria-hidden className="text-muted transition group-open:rotate-45">+</span>
          </summary>
          <div className="px-4 pb-4">
            <label className="sr-only" htmlFor="text">{t("trainingLabel")}</label>
            <textarea
              id="text" name="text" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)}
              aria-invalid={!!notesError} aria-describedby="text-error"
              className={`${inputClass} ${notesError ? "border-red-500/50" : ""}`}
              placeholder={t("trainingPlaceholder")}
            />
            <FieldError id="text-error">{notesError}</FieldError>
            {!notesError && notes.length > LIMITS.text_chars.training_text * 0.8 && (
              <p className="mt-2 text-xs text-muted tabular-nums">{t("characters", { n: notes.trim().length, max: LIMITS.text_chars.training_text })}</p>
            )}
          </div>
        </details>
        <div>
          <label className={labelClass} htmlFor="player">{t("player")}</label>
          <input
            id="player" name="player" placeholder={t("playerPlaceholder")} autoComplete="off" className={inputClass}
            maxLength={LIMITS.text_chars.player}
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="stroke_type">
            {t("stroke")} <span className="font-medium tracking-normal normal-case text-muted">{tAll("common.optional")}</span>
          </label>
          <div className="relative">
            <select id="stroke_type" name="stroke_type" defaultValue="" className={`${inputClass} appearance-none pr-12`}>
              <option value="">{t("autoDetect")}</option>
              {STROKE_TYPES.map((s) => <option key={s.value} value={s.value}>{tAll(`strokes.${s.value}`)}</option>)}
            </select>
            <ChevronIcon className="pointer-events-none absolute top-1/2 right-4 size-5 -translate-y-1/2 text-muted" />
          </div>
          <p className="mt-2 text-xs text-muted">{t("strokeHint")}</p>
        </div>
        <fieldset>
          <legend className={labelClass}>{t("hand")}</legend>
          <RadioTiles name="hand" options={HANDS.map((value) => ({ value, label: tAll(`hands.${value}`) }))} defaultValue="auto" className="grid-cols-3" />
          <p className="mt-2 text-xs text-muted">{t("handHint")}</p>
        </fieldset>
      </div>
      <SubmitBar label={t("submit")} progress={progress} error={error} startingLabel={starting} blocked={blocked} />
    </form>
      <ExampleSection
        before={{ src: "/examples/breakdown-before.mp4", label: tAll("common.before"), caption: t("beforeCaption"), vertical: true }}
        after={{ src: demoAssets.breakdown.url, label: tAll("common.after"), caption: tAll("demoDescriptions.breakdown"), vertical: true }}
        steps={STEPS.map((s) => t(`steps.${s}`))}
      />
    </>
  );
}
