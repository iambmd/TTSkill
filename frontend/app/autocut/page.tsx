"use client";

import demoAssets from "@/lib/demo-assets.json";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { submitJob } from "@/lib/submit";
import { LIMITS, rangeProblem } from "@/lib/validate";
import { FieldError, PageIntro, RadioTiles, SubmitBar, inputClass, labelClass, labelTextClass } from "../ui";
import { ExampleSection } from "../examples";
import { VideoPicker } from "../video-picker";

const MODES = [
  { value: "highlights", label: "Highlights", sub: "Best rallies, most shots first" },
  { value: "full", label: "Full match", sub: "Every rally, dead time cut" },
] as const;
const A = LIMITS.autocut;
// Detection settings: form name, label, default, whole numbers only.
const SETTINGS = [
  { name: "threshold", label: "Hit threshold", initial: "3.0", whole: false },
  { name: "gap", label: "Max gap (s)", initial: "1.6", whole: false },
  { name: "min_hits", label: "Min hits", initial: "4", whole: true },
] as const;

export default function AutoCutPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"highlights" | "full">("highlights");
  const [topN, setTopN] = useState(5);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [starting, setStarting] = useState("Starting...");
  const [videoProblem, setVideoProblem] = useState<string | null>(null);
  const [settings, setSettings] = useState<Record<string, string>>(
    Object.fromEntries(SETTINGS.map((s) => [s.name, s.initial])),
  );
  const settingErrors = SETTINGS.map((s) => rangeProblem(settings[s.name], s.name, s.label.replace(" (s)", ""), s.whole));
  const settingsError = settingErrors.find(Boolean) ?? null;
  const blocked = !!videoProblem || !!settingsError;

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
    for (const s of SETTINGS) if (!settings[s.name].trim()) form.delete(s.name); // blank = default
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
    <form onSubmit={onSubmit} noValidate className="mx-auto max-w-xl space-y-7">
      <PageIntro
        eyebrow="Match Auto-Cut"
        title="Cut the dead time."
        body="We hear every ball contact, find the rallies, and cut your match down to the points that count."
      />
      <VideoPicker
        kind="autocut" onProblem={setVideoProblem}
        title="Upload your match" hint="Phone footage works. Keep the sound on, that's how we find the rallies."
      />
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
            id="top_n" name="top_n" type="range" min={A.top_n.min} max={A.top_n.max} value={topN}
            onChange={(e) => setTopN(Number(e.target.value))} className="mt-3 h-8 w-full accent-accent"
          />
        </div>
      )}
      <details className="group rounded-2xl border border-line bg-panel">
        <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3.5 text-sm font-semibold [&::-webkit-details-marker]:hidden">
          Detection settings
          <span aria-hidden className="text-muted transition group-open:rotate-45">+</span>
        </summary>
        <div className="grid grid-cols-3 gap-3 px-4 [&>div]:flex [&>div]:flex-col [&>div]:justify-end">
          {SETTINGS.map((s, i) => (
            <div key={s.name}>
              <label className={labelClass} htmlFor={s.name}>{s.label}</label>
              <input
                id={s.name} name={s.name} type="text" inputMode={s.whole ? "numeric" : "decimal"} autoComplete="off"
                value={settings[s.name]} onChange={(e) => setSettings({ ...settings, [s.name]: e.target.value })}
                aria-invalid={!!settingErrors[i]} aria-describedby="settings-error"
                className={`${inputClass} ${settingErrors[i] ? "border-red-500/50" : ""}`}
              />
            </div>
          ))}
        </div>
        <div className="px-4 pb-4">
          <FieldError id="settings-error">{settingsError}</FieldError>
          {!settingsError && (
            <p className="mt-3 text-xs text-muted">
              Threshold {A.threshold.min}–{A.threshold.max}, gap {A.gap.min}–{A.gap.max} s, min hits {A.min_hits.min}–{A.min_hits.max}.
              Not finding rallies? Lower the threshold.
            </p>
          )}
        </div>
      </details>
      <SubmitBar label="Cut my match" progress={progress} error={error} startingLabel={starting} blocked={blocked} />
    </form>
      <ExampleSection
        before={{ src: "/examples/autocut-before.mp4", label: "Before", caption: "A 3.5-minute phone recording of a match" }}
        after={{ src: demoAssets.autocut.url, label: "After", caption: `Highlights: the top 4 rallies, ${Math.round(demoAssets.autocut.duration)} s` }}
        steps={[
          "We listen to the match. Ball contact makes a short, sharp click in the 2–6 kHz range, so we filter the sound to that band.",
          "Every spike well above the background noise counts as a hit. Long sounds like shoe squeaks are ignored.",
          "Hits close together are grouped into rallies. A rally needs at least 4 hits, so a single bounce doesn't count.",
          "Highlights keeps the rallies with the most hits. Full match keeps every rally and drops the time in between.",
          "Each rally gets 1.5 s of padding so you see the serve and the finish, then the clips are joined into one video.",
        ]}
      />
    </>
  );
}
