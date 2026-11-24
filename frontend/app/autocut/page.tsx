"use client";

import demoAssets from "@/lib/demo-assets.json";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { submitJob } from "@/lib/submit";
import { LIMITS } from "@/lib/validate";
import { PageIntro, RadioTiles, SubmitBar, labelClass, labelTextClass } from "../ui";
import { ExampleSection } from "../examples";
import { VideoPicker } from "../video-picker";

const MODES = ["highlights", "full"] as const;
const STEPS = ["one", "two", "three"] as const;
const A = LIMITS.autocut;
export default function AutoCutPage() {
  const t = useTranslations("autocut");
  const tAll = useTranslations();
  const router = useRouter();
  const [mode, setMode] = useState<"highlights" | "full">("highlights");
  const [topN, setTopN] = useState(5);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [starting, setStarting] = useState(tAll("common.starting"));
  const [videoProblem, setVideoProblem] = useState<string | null>(null);
  const blocked = !!videoProblem;

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (blocked) return;
    const form = new FormData(e.currentTarget);
    const video = form.get("video") as File | null;
    const url = String(form.get("url") ?? "").trim();
    const hasVideo = !!video && video.size > 0;
    if (!hasVideo && !url) {
      setError(tAll("validation.autocutVideo"));
      return;
    }
    if (!hasVideo) form.delete("video");
    if (hasVideo || !url) form.delete("url");
    form.set("mode", mode);
    if (mode === "full") form.delete("top_n");
    setStarting(form.has("url") ? tAll("common.checkingLink") : tAll("common.starting"));
    setProgress(0);
    setError(null);
    try {
      const job = await submitJob("autocut", form, setProgress, tAll);
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
      <VideoPicker
        kind="autocut" onProblem={setVideoProblem}
        title={t("videoTitle")} hint={t("videoHint")}
      />
      <div className="min-w-0 space-y-6">
        <fieldset>
          <legend className={labelClass}>{t("whatToMake")}</legend>
          <RadioTiles name="mode" options={MODES.map((value) => ({ value, label: t(`modes.${value}`), sub: t(`modes.${value}Sub`) }))} value={mode} onChange={setMode} className="grid-cols-2" />
        </fieldset>
        {mode === "highlights" && (
          <div className="surface-card p-4">
            <div className="flex items-end justify-between">
              <label className={labelTextClass} htmlFor="top_n">{t("topN")}</label>
              <span className="stat text-4xl text-accent">{topN}</span>
            </div>
            <input
              id="top_n" name="top_n" type="range" min={A.top_n.min} max={A.top_n.max} value={topN}
              onChange={(e) => setTopN(Number(e.target.value))} className="mt-3 h-11 w-full accent-accent sm:h-8"
            />
          </div>
        )}
      </div>
      <SubmitBar label={t("submit")} progress={progress} error={error} startingLabel={starting} blocked={blocked} />
    </form>
      <ExampleSection
        before={{ src: "/examples/autocut-before.mp4", label: tAll("common.before"), caption: t("beforeCaption") }}
        after={{ src: demoAssets.autocut.url, label: tAll("common.after"), caption: tAll("demoDescriptions.autocut") }}
        steps={STEPS.map((s) => t(`steps.${s}`))}
      />
    </>
  );
}
