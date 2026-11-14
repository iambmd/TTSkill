"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { submitJob } from "@/lib/submit";
import { buttonClass, inputClass, labelClass } from "../ui";

const STROKES = ["forehand", "backhand", "serve", "flick", "block", "footwork"] as const;

export default function BreakdownPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const video = form.get("video") as File | null;
    const text = String(form.get("text") ?? "").trim();
    if ((!video || video.size === 0) && !text) {
      setError("Upload a video or describe the player's training.");
      return;
    }
    if (video && video.size === 0) form.delete("video");
    setBusy(true);
    setError(null);
    try {
      const job = await submitJob("/api/jobs/breakdown", form);
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Technique Breakdown</h1>
        <p className="text-sm text-white/70">Give us a clip or a description, and we will build a coaching video.</p>
      </div>
      <div>
        <label className={labelClass} htmlFor="player">Player</label>
        <input id="player" name="player" placeholder="e.g. Fan Zhendong" className={inputClass} />
      </div>
      <div>
        <label className={labelClass} htmlFor="video">Training video</label>
        <input id="video" name="video" type="file" accept="video/*" className={inputClass} />
      </div>
      <div>
        <label className={labelClass} htmlFor="text">Or describe the training</label>
        <textarea id="text" name="text" rows={4} className={inputClass}
          placeholder="Paste notes, a transcript, or a description of how the player trains this stroke." />
      </div>
      <fieldset>
        <legend className={labelClass}>Stroke</legend>
        <div className="flex flex-wrap gap-2">
          {STROKES.map((s, i) => (
            <label key={s} className="cursor-pointer">
              <input type="radio" name="stroke" value={s} defaultChecked={i === 0} className="peer sr-only" />
              <span className="block rounded-full border border-white/15 px-4 py-1.5 text-sm capitalize peer-checked:border-accent peer-checked:text-accent">
                {s}
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={busy} className={buttonClass}>
        {busy ? "Submitting..." : "Generate breakdown"}
      </button>
    </form>
  );
}
