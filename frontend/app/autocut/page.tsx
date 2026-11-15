"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { submitJob } from "@/lib/submit";
import { LINK_HINT, youtubeId } from "@/lib/youtube";
import { PageIntro, RadioTiles, SubmitBar, inputClass, labelClass, labelTextClass } from "../ui";
import { VideoPicker } from "../video-picker";

const MODES = [
  { value: "highlights", label: "Highlights", sub: "Best rallies, most shots first" },
  { value: "full", label: "Full match", sub: "Every rally, dead time cut" },
] as const;

export default function AutoCutPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"highlights" | "full">("highlights");
  const [topN, setTopN] = useState(5);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [starting, setStarting] = useState("Starting...");

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const video = form.get("video") as File | null;
    const url = String(form.get("url") ?? "").trim();
    const hasVideo = !!video && video.size > 0;
    if (!hasVideo && !url) {
      setError("Upload a match video or paste a YouTube link.");
      return;
    }
    if (!hasVideo && !youtubeId(url)) {
      setError(LINK_HINT);
      return;
    }
    if (!hasVideo) form.delete("video");
    if (hasVideo || !url) form.delete("url");
    form.set("mode", mode);
    if (mode === "full") form.delete("top_n");
    setStarting(form.has("url") ? "Checking the link..." : "Starting...");
    setProgress(0);
    setError(null);
    try {
      const job = await submitJob("/api/jobs/autocut", form, setProgress);
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError((err as Error).message);
      setProgress(null);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto max-w-xl space-y-7">
      <PageIntro
        eyebrow="Match Auto-Cut"
        title="Cut the dead time."
        body="We hear every ball contact, find the rallies, and cut your match down to the points that count."
      />
      <VideoPicker title="Upload your match" hint="Phone footage works. Keep the sound on, that's how we find the rallies." />
      <fieldset>
        <legend className={labelClass}>What to make</legend>
        <RadioTiles name="mode" options={MODES} value={mode} onChange={setMode} className="grid-cols-2" />
      </fieldset>
      {mode === "highlights" && (
        <div className="rounded-2xl border border-line bg-panel p-4">
          <div className="flex items-end justify-between">
            <label className={labelTextClass} htmlFor="top_n">Rallies in the reel</label>
            <span className="headline text-5xl text-accent">{topN}</span>
          </div>
          <input
            id="top_n" name="top_n" type="range" min={1} max={20} value={topN}
            onChange={(e) => setTopN(Number(e.target.value))} className="mt-3 h-8 w-full accent-accent"
          />
        </div>
      )}
      <details className="group rounded-2xl border border-line bg-panel">
        <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3.5 text-sm font-semibold [&::-webkit-details-marker]:hidden">
          Detection settings
          <span aria-hidden className="text-muted transition group-open:rotate-45">+</span>
        </summary>
        <div className="grid grid-cols-3 gap-3 px-4 pb-4 [&>div]:flex [&>div]:flex-col [&>div]:justify-end">
          <div>
            <label className={labelClass} htmlFor="threshold">Hit threshold</label>
            <input id="threshold" name="threshold" type="number" inputMode="decimal" step="0.1" defaultValue={3.0} className={inputClass} />
          </div>
          <div>
            <label className={labelClass} htmlFor="gap">Max gap (s)</label>
            <input id="gap" name="gap" type="number" inputMode="decimal" step="0.1" defaultValue={1.6} className={inputClass} />
          </div>
          <div>
            <label className={labelClass} htmlFor="min_hits">Min hits</label>
            <input id="min_hits" name="min_hits" type="number" inputMode="numeric" defaultValue={4} className={inputClass} />
          </div>
        </div>
      </details>
      <SubmitBar label="Cut my match" progress={progress} error={error} startingLabel={starting} />
    </form>
  );
}
