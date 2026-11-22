"use client";

import demoAssets from "@/lib/demo-assets.json";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { submitJob } from "@/lib/submit";
import { LIMITS } from "@/lib/validate";
import { PageIntro, RadioTiles, SubmitBar, labelClass, labelTextClass } from "../ui";
import { ExampleSection } from "../examples";
import { demoDescriptions } from "@/lib/demo-descriptions";
import { VideoPicker } from "../video-picker";

const MODES = [
  { value: "highlights", label: "Highlights", sub: "A short reel of your best rallies" },
  { value: "full", label: "Full match", sub: "Every rally, dead time cut" },
] as const;
const A = LIMITS.autocut;
export default function AutoCutPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"highlights" | "full">("highlights");
  const [topN, setTopN] = useState(5);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [starting, setStarting] = useState("Starting...");
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
      setError("Upload a match video or paste a YouTube link.");
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
      const job = await submitJob("autocut", form, setProgress);
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
        eyebrow="Match Auto-Cut"
        title="Cut the dead time."
        body="Turn a match recording into a short reel or keep every rally."
      />
      <VideoPicker
        kind="autocut" onProblem={setVideoProblem}
        title="Upload your match" hint="A phone recording of your match works."
      />
      <div className="min-w-0 space-y-6">
        <fieldset>
          <legend className={labelClass}>What to make</legend>
          <RadioTiles name="mode" options={MODES} value={mode} onChange={setMode} className="grid-cols-2" />
        </fieldset>
        {mode === "highlights" && (
          <div className="surface-card p-4">
            <div className="flex items-end justify-between">
              <label className={labelTextClass} htmlFor="top_n">Rallies in the reel</label>
              <span className="text-4xl font-bold tabular-nums text-accent">{topN}</span>
            </div>
            <input
              id="top_n" name="top_n" type="range" min={A.top_n.min} max={A.top_n.max} value={topN}
              onChange={(e) => setTopN(Number(e.target.value))} className="mt-3 h-11 w-full accent-accent sm:h-8"
            />
          </div>
        )}
      </div>
      <SubmitBar label="Cut my match" progress={progress} error={error} startingLabel={starting} blocked={blocked} />
    </form>
      <ExampleSection
        before={{ src: "/examples/autocut-before.mp4", label: "Before", caption: "A phone records both players as they serve, rally and get ready for the next point." }}
        after={{ src: demoAssets.autocut.url, label: "After", caption: demoDescriptions.autocut }}
        steps={[
          "Upload your match or paste a video link.",
          "Choose a highlight reel or a cut of every rally.",
          "Watch the result and download it to share.",
        ]}
      />
    </>
  );
}
