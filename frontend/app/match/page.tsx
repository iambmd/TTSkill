"use client";

import demoAssets from "@/lib/demo-assets.json";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { submitJob } from "@/lib/submit";
import { feetInches, heightProblem, LIMITS } from "@/lib/validate";
import { FieldError, PageIntro, RadioTiles, SubmitBar, inputClass, labelClass } from "../ui";
import { ExampleSection } from "../examples";
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
const GRIPS = [
  { value: "shakehand", label: "Shakehand", sub: "Handshake grip, most players" },
  { value: "penhold", label: "Penhold", sub: "Held like a pen" },
] as const;
const UNITS = [
  { value: "cm", label: "cm" },
  { value: "ft", label: "ft / in" },
] as const;

const optional = <span className="font-medium tracking-normal normal-case text-white/40">optional</span>;
const unitTag = (u: string) => (
  <span className="pointer-events-none absolute top-1/2 right-4 -translate-y-1/2 text-sm font-semibold text-muted">{u}</span>
);

export default function MatchPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [starting, setStarting] = useState("Starting...");
  const [videoProblem, setVideoProblem] = useState<string | null>(null);
  const [unit, setUnit] = useState<"cm" | "ft">("cm");
  const [cm, setCm] = useState("");
  const [ft, setFt] = useState("");
  const [inch, setInch] = useState("");

  const imperial = feetInches(ft, inch);
  const heightError = unit === "cm" ? heightProblem(cm) : imperial.error;
  const heightCm = unit === "cm" ? (cm.trim() ? cm.trim() : null) : imperial.cm !== null ? String(imperial.cm) : null;

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (videoProblem || heightError) return;
    const form = new FormData(e.currentTarget);
    const video = form.get("video") as File | null;
    const url = String(form.get("url") ?? "").trim();
    const hasVideo = !!video && video.size > 0;
    if (!hasVideo && !url) {
      setError("Upload a clip of yourself or paste a YouTube link.");
      return;
    }
    if (!hasVideo) form.delete("video");
    if (hasVideo || !url) form.delete("url");
    if (heightCm) form.set("height_cm", heightCm);
    else form.delete("height_cm");
    setStarting(form.has("url") ? "Checking the link..." : "Starting...");
    setProgress(0);
    setError(null);
    try {
      const job = await submitJob("match", form, setProgress);
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
        eyebrow="Find my pro match"
        title="Who do you play like?"
        body="Film yourself hitting a few strokes. We match your height, build and swing to the closest pros and show you their breakdowns."
      />
      <VideoPicker findPlayer
        kind="match" onProblem={setVideoProblem}
        title="Upload your swing" hint="Full body in frame, a few forehands or backhands. Side-on with the table visible works best."
      />
      <fieldset>
        <legend className={labelClass}>Stroke to compare</legend>
        <RadioTiles name="stroke" options={STROKES} defaultValue="forehand" className="grid-cols-2" />
      </fieldset>
      <fieldset>
        <legend className={labelClass}>Your grip</legend>
        <RadioTiles name="grip" options={GRIPS} defaultValue="shakehand" className="grid-cols-2" />
        <p className="mt-2 text-xs text-muted">Pros with your grip come first.</p>
      </fieldset>
      <div>
        <div className="mb-2 flex items-center justify-between gap-3">
          <label className={`${labelClass} mb-0`} htmlFor={unit === "cm" ? "height_cm" : "height_ft"}>
            Your height {optional}
          </label>
          <div role="radiogroup" aria-label="Height unit" className="flex rounded-lg border border-line p-0.5 text-xs font-bold">
            {UNITS.map((u) => (
              <button
                key={u.value} type="button" role="radio" aria-checked={unit === u.value} onClick={() => setUnit(u.value)}
                className={`h-9 rounded-md px-3 ${unit === u.value ? "bg-accent text-black" : "text-muted hover:text-white"}`}
              >
                {u.label}
              </button>
            ))}
          </div>
        </div>
        {unit === "cm" ? (
          <div className="relative">
            <input
              id="height_cm" type="text" inputMode="decimal" autoComplete="off" value={cm} onChange={(e) => setCm(e.target.value)}
              placeholder="e.g. 175" aria-invalid={!!heightError} aria-describedby="height-error"
              className={`${inputClass} pr-14 ${heightError ? "border-red-500/50" : ""}`}
            />
            {unitTag("cm")}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <div className="relative">
              <input
                id="height_ft" type="text" inputMode="numeric" autoComplete="off" value={ft} onChange={(e) => setFt(e.target.value)}
                placeholder="5" aria-label="Feet" aria-invalid={!!heightError} aria-describedby="height-error"
                className={`${inputClass} pr-12 ${heightError ? "border-red-500/50" : ""}`}
              />
              {unitTag("ft")}
            </div>
            <div className="relative">
              <input
                type="text" inputMode="decimal" autoComplete="off" value={inch} onChange={(e) => setInch(e.target.value)}
                placeholder="10" aria-label="Inches" aria-invalid={!!heightError} aria-describedby="height-error"
                className={`${inputClass} pr-12 ${heightError ? "border-red-500/50" : ""}`}
              />
              {unitTag("in")}
            </div>
          </div>
        )}
        <FieldError id="height-error">{heightError}</FieldError>
        {!heightError && (
          <p className="mt-2 text-xs text-muted">
            {LIMITS.height_cm.min}–{LIMITS.height_cm.max} cm. Leave it empty and we estimate it from the table in the frame (76 cm high, 274 cm long).
          </p>
        )}
      </div>
      <fieldset>
        <legend className={labelClass}>Bat hand</legend>
        <RadioTiles name="hand" options={HANDS} defaultValue="auto" className="grid-cols-3" />
      </fieldset>
      <SubmitBar
        label="Find my match" progress={progress} error={error} startingLabel={starting}
        blocked={!!videoProblem || !!heightError}
      />
    </form>
      <ExampleSection
        before={{ src: "/examples/match-before.mp4", label: "Before", caption: "A player filming their forehand" }}
        after={{ src: demoAssets.match.url, label: "After", caption: "The pro matches video we made from it", vertical: true }}
        steps={[
          "We track your body with pose detection and measure your build: limb lengths compared with your height, and how wide you stand.",
          "If you don't give your height, we estimate it from the table in the frame, which is always 76 cm high and 274 cm long.",
          "We compare you only with pros who play with the same hand, and pros with your grip come first.",
          "The 3 pros closest to your height and build are your matches. We then line up your swing against each of theirs to show where your form differs.",
          "You get a score and notes for each pro, plus one video of their technique breakdowns to learn from.",
        ]}
      />
    </>
  );
}
