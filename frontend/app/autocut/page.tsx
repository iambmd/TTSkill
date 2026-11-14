"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { submitJob } from "@/lib/submit";
import { buttonClass, inputClass, labelClass } from "../ui";

export default function AutoCutPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"highlights" | "full">("highlights");
  const [topN, setTopN] = useState(5);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const video = form.get("video") as File | null;
    if (!video || video.size === 0) {
      setError("Upload a match video.");
      return;
    }
    form.set("mode", mode);
    if (mode === "full") form.delete("top_n");
    setBusy(true);
    setError(null);
    try {
      const job = await submitJob("/api/jobs/autocut", form);
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Match Auto-Cut</h1>
        <p className="text-sm text-white/70">We find rallies from the sound of the ball and cut out the dead time.</p>
      </div>
      <div>
        <label className={labelClass} htmlFor="video">Match video</label>
        <input id="video" name="video" type="file" accept="video/*" className={inputClass} />
      </div>
      <div className="flex gap-2">
        {(["highlights", "full"] as const).map((m) => (
          <button key={m} type="button" onClick={() => setMode(m)}
            className={`rounded-full border px-4 py-1.5 text-sm ${mode === m ? "border-accent text-accent" : "border-white/15"}`}>
            {m === "highlights" ? "Highlights" : "Full match"}
          </button>
        ))}
      </div>
      {mode === "highlights" && (
        <div>
          <label className={labelClass} htmlFor="top_n">Top {topN} rallies (by shot count)</label>
          <input id="top_n" name="top_n" type="range" min={1} max={20} value={topN}
            onChange={(e) => setTopN(Number(e.target.value))} className="w-full accent-[#ff6b2c]" />
        </div>
      )}
      <details className="rounded-lg border border-white/10 p-4">
        <summary className="cursor-pointer text-sm font-medium">Advanced detection settings</summary>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <div>
            <label className={labelClass} htmlFor="threshold">Hit threshold</label>
            <input id="threshold" name="threshold" type="number" step="0.1" defaultValue={3.0} className={inputClass} />
          </div>
          <div>
            <label className={labelClass} htmlFor="gap">Max gap (s)</label>
            <input id="gap" name="gap" type="number" step="0.1" defaultValue={1.6} className={inputClass} />
          </div>
          <div>
            <label className={labelClass} htmlFor="min_hits">Min hits</label>
            <input id="min_hits" name="min_hits" type="number" defaultValue={4} className={inputClass} />
          </div>
        </div>
      </details>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={busy} className={buttonClass}>
        {busy ? "Uploading..." : "Cut my match"}
      </button>
    </form>
  );
}
