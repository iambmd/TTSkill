"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { submitJob } from "@/lib/submit";
import { LINK_HINT, youtubeId } from "@/lib/youtube";
import { PageIntro, RadioTiles, SubmitBar, inputClass, labelClass } from "../ui";
import { VideoPicker } from "../video-picker";

const STROKES = [
  { value: "forehand", label: "Forehand" },
  { value: "backhand", label: "Backhand" },
] as const;
const HANDS = [
  { value: "auto", label: "Auto" },
  { value: "right", label: "Right" },
  { value: "left", label: "Left" },
] as const;

export default function MatchPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const video = form.get("video") as File | null;
    const url = String(form.get("url") ?? "").trim();
    const hasVideo = !!video && video.size > 0;
    if (!hasVideo && !url) {
      setError("Upload a clip of yourself or paste a YouTube link.");
      return;
    }
    if (!hasVideo && !youtubeId(url)) {
      setError(LINK_HINT);
      return;
    }
    if (!hasVideo) form.delete("video");
    if (hasVideo || !url) form.delete("url");
    setProgress(0);
    setError(null);
    try {
      const job = await submitJob("/api/jobs/match", form, setProgress);
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError((err as Error).message);
      setProgress(null);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto max-w-xl space-y-7">
      <PageIntro
        eyebrow="Find my pro match"
        title="Who do you play like?"
        body="Film yourself hitting a few strokes. We match your height, build and swing to the closest pros and show you their breakdowns."
      />
      <VideoPicker title="Upload your swing" hint="Full body in frame, a few forehands or backhands. Side-on with the table visible works best." />
      <fieldset>
        <legend className={labelClass}>Stroke to compare</legend>
        <RadioTiles name="stroke" options={STROKES} defaultValue="forehand" className="grid-cols-2" />
      </fieldset>
      <div>
        <label className={labelClass} htmlFor="height_cm">
          Your height <span className="font-medium tracking-normal normal-case text-white/40">optional</span>
        </label>
        <div className="relative">
          <input
            id="height_cm" name="height_cm" type="number" inputMode="numeric" min={100} max={230} step={1}
            placeholder="e.g. 175" className={`${inputClass} pr-14`}
          />
          <span className="pointer-events-none absolute top-1/2 right-4 -translate-y-1/2 text-sm font-semibold text-muted">cm</span>
        </div>
        <p className="mt-2 text-xs text-muted">Leave it empty and we estimate it from the table in the frame (76 cm high, 274 cm long).</p>
      </div>
      <fieldset>
        <legend className={labelClass}>Bat hand</legend>
        <RadioTiles name="hand" options={HANDS} defaultValue="auto" className="grid-cols-3" />
      </fieldset>
      <SubmitBar label="Find my match" progress={progress} error={error} />
    </form>
  );
}
