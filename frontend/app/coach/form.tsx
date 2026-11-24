"use client";

import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useRef, useState } from "react";
import { submitJob, type RallyClip } from "@/lib/submit";
import { LIMITS, textProblem } from "@/lib/validate";
import { FieldError, PageIntro, SubmitBar, inputClass, labelClass } from "../ui";
import { VideoPicker } from "../video-picker";
import { MatchSource } from "../match-source";
import { CoachExample } from "./example";

const EXAMPLES = ["one", "two", "three"] as const;

export default function CoachForm({ sourceJob, rallyId, clip }: { sourceJob?: string; rallyId?: string; clip?: RallyClip }) {
  const t = useTranslations("coach");
  const tc = useTranslations("common");
  const tv = useTranslations("validation");
  const te = useTranslations("errors");
  const tAll = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const askRef = useRef<HTMLTextAreaElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [starting, setStarting] = useState(tc("starting"));
  const [ask, setAsk] = useState(sourceJob && rallyId ? t("rallyRequest") : "");
  const [videoProblem, setVideoProblem] = useState<string | null>(null);
  const most = LIMITS.text_chars.coach_request;
  const length = ask.trim().length;
  const askError = textProblem(ask, "coach_request", tv("labels.request"), tv);
  // An empty or whitespace-only request is ignored, like an empty chat message: nothing to send.
  const blocked = length === 0 || !!askError || !!videoProblem;

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (blocked) {
      if (length === 0) askRef.current?.focus();
      return;
    }
    const form = new FormData(e.currentTarget);
    const video = form.get("video") as File | null;
    const url = String(form.get("url") ?? "").trim();
    const hasVideo = !!video && video.size > 0;
    form.set("request", ask.trim());
    if (!hasVideo && !url && !sourceJob) {
      setError(tv("coachVideo"));
      return;
    }
    if (!hasVideo) form.delete("video");
    if (hasVideo || !url) form.delete("url");
    setStarting(form.has("url") ? tc("checkingLink") : tc("starting"));
    setProgress(0);
    setError(null);
    try {
      const job = await submitJob("coach", form, setProgress, te);
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError((err as Error).message);
      setProgress(null);
    }
  }

  return (
    <>
      <form onSubmit={onSubmit} noValidate className="coach-surface coach-form feature-form">
        <PageIntro
          eyebrow={t("eyebrow")}
          title={t("title")}
          body={t("body")}
        />
        {/* The coach writes its notes, cards and video text in the page's language. */}
        <input type="hidden" name="lang" value={locale} />
        <div className="coach-request">
          <div className="flex items-end justify-between">
            <label className={labelClass} htmlFor="request">{t("ask")}</label>
            <span aria-hidden className={`mb-2 text-xs tabular-nums ${askError ? "font-bold text-red-200" : "text-muted"}`}>
              {length}/{most}
            </span>
          </div>
          <textarea
            ref={askRef} id="request" name="request" rows={3} value={ask} onChange={(e) => setAsk(e.target.value)}
            aria-invalid={!!askError} aria-describedby="request-error"
            className={`${inputClass} ${askError ? "border-red-500/50" : ""}`}
            placeholder={t("placeholder")}
          />
          <FieldError id="request-error">{askError}</FieldError>
          <div className="coach-prompts mt-3 grid gap-2">
            {EXAMPLES.map((key) => t(`examples.${key}`)).map((x) => (
              <button
                key={x} type="button"
                onClick={() => { setAsk(x); askRef.current?.focus(); }}
                className="min-h-12 border px-3 py-2 text-left text-sm font-semibold"
              >
                {x}
              </button>
            ))}
          </div>
        </div>
        <div className="coach-upload">
          {sourceJob ? <MatchSource job={sourceJob} rallyId={rallyId} clip={clip} form="coach" /> : (
            <VideoPicker findPlayer onlyMeOption kind="coach" onProblem={setVideoProblem} title={t("videoTitle")} hint={t("videoHint")} />
          )}
        </div>
        <SubmitBar
          label={t("submit")} progress={progress} error={error} startingLabel={starting}
          blocked={blocked} blockedHint={tAll("submit.blockedHint")}
        />
      </form>
      <div className="coach-surface coach-example"><CoachExample /></div>
    </>
  );
}
