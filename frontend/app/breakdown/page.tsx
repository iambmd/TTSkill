"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { submitJob } from "@/lib/submit";
import { LINK_HINT, youtubeId } from "@/lib/youtube";
import { PageIntro, RadioTiles, SubmitBar, inputClass, labelClass } from "../ui";
import { VideoPicker } from "../video-picker";

const STROKES = ["forehand", "backhand", "serve", "flick", "block", "footwork"].map((s) => ({ value: s, label: s }));
const HANDS = [
  { value: "auto", label: "Auto" },
  { value: "right", label: "Right" },
  { value: "left", label: "Left" },
];

export default function BreakdownPage() {
  const router = useRouter();
  const textRef = useRef<HTMLDetailsElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const video = form.get("video") as File | null;
    const url = String(form.get("url") ?? "").trim();
    const text = String(form.get("text") ?? "").trim();
    const hasVideo = !!video && video.size > 0;
    if (!hasVideo && !url && !text) {
      setError("Upload a clip, paste a YouTube link, or describe the player's training instead.");
      if (textRef.current) textRef.current.open = true;
      return;
    }
    if (!hasVideo && url && !youtubeId(url)) {
      setError(LINK_HINT);
      return;
    }
    if (!hasVideo) form.delete("video");
    if (hasVideo || !url) form.delete("url");
    setProgress(0);
    setError(null);
    try {
      const job = await submitJob("/api/jobs/breakdown", form, setProgress);
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError((err as Error).message);
      setProgress(null);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto max-w-xl space-y-7">
      <PageIntro
        eyebrow="Technique Breakdown"
        title="Swing like the pros."
        body="Drop in a clip of a player you admire, pick the stroke, and get a step-by-step coaching video."
      />
      <VideoPicker title="Upload a clip" hint="A few seconds of the stroke. Side-on, full body in frame works best." />
      <details ref={textRef} className="group rounded-2xl border border-line bg-panel">
        <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3.5 text-sm font-semibold [&::-webkit-details-marker]:hidden">
          No video? Describe the training instead
          <span aria-hidden className="text-muted transition group-open:rotate-45">+</span>
        </summary>
        <div className="px-4 pb-4">
          <label className="sr-only" htmlFor="text">Training description</label>
          <textarea
            id="text" name="text" rows={4} className={inputClass}
            placeholder="Paste notes, a transcript, or a description of how the player trains this stroke."
          />
        </div>
      </details>
      <div>
        <label className={labelClass} htmlFor="player">Player</label>
        <input id="player" name="player" placeholder="e.g. Fan Zhendong" autoComplete="off" className={inputClass} />
      </div>
      <fieldset>
        <legend className={labelClass}>Stroke</legend>
        <RadioTiles name="stroke" options={STROKES} defaultValue="forehand" className="grid-cols-3" />
      </fieldset>
      <fieldset>
        <legend className={labelClass}>Bat hand</legend>
        <RadioTiles name="hand" options={HANDS} defaultValue="auto" className="grid-cols-3" />
        <p className="mt-2 text-xs text-muted">Auto finds the paddle in the video. Pick a hand if the overlay tracks the wrong arm.</p>
      </fieldset>
      <SubmitBar label="Break it down" progress={progress} error={error} />
    </form>
  );
}
