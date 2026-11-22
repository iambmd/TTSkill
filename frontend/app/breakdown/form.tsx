"use client";

import demoAssets from "@/lib/demo-assets.json";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { submitJob } from "@/lib/submit";
import { STROKE_TYPES } from "@/lib/strokes";
import { LIMITS, textProblem } from "@/lib/validate";
import { ChevronIcon, FieldError, PageIntro, RadioTiles, SubmitBar, inputClass, labelClass } from "../ui";
import { ExampleSection } from "../examples";
import { VideoPicker } from "../video-picker";
import { MatchSource } from "../match-source";

const HANDS = [
  { value: "auto", label: "Auto" },
  { value: "right", label: "Right" },
  { value: "left", label: "Left" },
];

export default function BreakdownForm({ sourceJob }: { sourceJob?: string }) {
  const router = useRouter();
  const textRef = useRef<HTMLDetailsElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [starting, setStarting] = useState("Starting...");
  const [videoProblem, setVideoProblem] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const notesError = textProblem(notes, "training_text", "The description");
  const blocked = !!videoProblem || !!notesError;

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (blocked) return;
    const form = new FormData(e.currentTarget);
    const video = form.get("video") as File | null;
    const url = String(form.get("url") ?? "").trim();
    const text = String(form.get("text") ?? "").trim();
    const hasVideo = !!video && video.size > 0;
    if (!hasVideo && !url && !sourceJob && !text) {
      setError("Upload a clip, paste a YouTube link, or describe the player's training instead.");
      if (textRef.current) textRef.current.open = true;
      return;
    }
    if (!hasVideo) form.delete("video");
    if (hasVideo || !url) form.delete("url");
    setStarting(form.has("url") ? "Checking the link..." : "Starting...");
    setProgress(0);
    setError(null);
    try {
      const job = await submitJob("breakdown", form, setProgress);
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
        eyebrow="Technique Breakdown"
        title="Swing like the pros."
        body="Drop in a clip of a player you admire and get a step-by-step coaching video of their stroke."
      />
      {sourceJob ? <MatchSource job={sourceJob} form="breakdown" /> : (
        <VideoPicker findPlayer onlyMeOption
          kind="breakdown" onProblem={setVideoProblem}
          title="Upload a clip" hint="A few seconds of the stroke. Side-on, full body in frame works best."
        />
      )}
      <div className="min-w-0 space-y-6">
        <details ref={textRef} className="group surface-card">
          <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3.5 text-sm font-semibold [&::-webkit-details-marker]:hidden">
            No video? Describe the training instead
            <span aria-hidden className="text-muted transition group-open:rotate-45">+</span>
          </summary>
          <div className="px-4 pb-4">
            <label className="sr-only" htmlFor="text">Training description</label>
            <textarea
              id="text" name="text" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)}
              aria-invalid={!!notesError} aria-describedby="text-error"
              className={`${inputClass} ${notesError ? "border-red-500/50" : ""}`}
              placeholder="Paste notes, a transcript, or a description of how the player trains this stroke."
            />
            <FieldError id="text-error">{notesError}</FieldError>
            {!notesError && notes.length > LIMITS.text_chars.training_text * 0.8 && (
              <p className="mt-2 text-xs text-muted tabular-nums">{notes.trim().length}/{LIMITS.text_chars.training_text} characters</p>
            )}
          </div>
        </details>
        <div>
          <label className={labelClass} htmlFor="player">Player</label>
          <input
            id="player" name="player" placeholder="e.g. Fan Zhendong" autoComplete="off" className={inputClass}
            maxLength={LIMITS.text_chars.player}
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="stroke_type">
            Stroke <span className="font-medium tracking-normal normal-case text-muted">optional</span>
          </label>
          <div className="relative">
            <select id="stroke_type" name="stroke_type" defaultValue="" className={`${inputClass} appearance-none pr-12`}>
              <option value="">Auto-detect from the swing</option>
              {STROKE_TYPES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
            <ChevronIcon className="pointer-events-none absolute top-1/2 right-4 size-5 -translate-y-1/2 text-muted" />
          </div>
          <p className="mt-2 text-xs text-muted">Pick one to get that stroke&apos;s coaching steps, or leave it and we read it from the video.</p>
        </div>
        <fieldset>
          <legend className={labelClass}>Bat hand</legend>
          <RadioTiles name="hand" options={HANDS} defaultValue="auto" className="grid-cols-3" />
          <p className="mt-2 text-xs text-muted">Auto finds the paddle in the video. Pick a hand if the overlay tracks the wrong arm.</p>
        </fieldset>
      </div>
      <SubmitBar label="Break it down" progress={progress} error={error} startingLabel={starting} blocked={blocked} />
    </form>
      <ExampleSection
        before={{ src: "/examples/breakdown-before.mp4", label: "Before", caption: "Ma Long forehand practice, 15 s", vertical: true }}
        after={{ src: demoAssets.breakdown.url, label: "After", caption: "The coaching video we made from it", vertical: true }}
        steps={[
          "We find the few seconds where the swing happens and track the player's body with pose detection, frame by frame.",
          "We work out which hand holds the bat and which stroke it is, unless you picked one.",
          "We pick the key moments of the swing: the backswing, the contact and the follow-through.",
          "AI turns those moments into three short cues, like \"Turn waist\" or \"Brush up\", plus a practice drill.",
          "We render a vertical coaching video: slow motion into each cue, a freeze frame, and a coloured trail on the bat hand.",
        ]}
      />
    </>
  );
}
