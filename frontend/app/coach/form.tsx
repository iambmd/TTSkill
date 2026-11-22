"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { submitJob } from "@/lib/submit";
import { LIMITS, textProblem } from "@/lib/validate";
import { FieldError, PageIntro, SubmitBar, inputClass, labelClass } from "../ui";
import { VideoPicker } from "../video-picker";
import { MatchSource } from "../match-source";
import { CoachExample } from "./example";

const EXAMPLES = [
  "Here's my match: show my best rallies and fix my forehand",
  "Which pros do I play like? Compare my backhand",
  "Cut the dead time and tell me what to work on",
];

export default function CoachForm({ sourceJob }: { sourceJob?: string }) {
  const router = useRouter();
  const askRef = useRef<HTMLTextAreaElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [starting, setStarting] = useState("Starting...");
  const [ask, setAsk] = useState("");
  const [videoProblem, setVideoProblem] = useState<string | null>(null);
  const most = LIMITS.text_chars.coach_request;
  const length = ask.trim().length;
  const askError = textProblem(ask, "coach_request", "Your request");
  // An empty or whitespace-only request is ignored, like an empty chat message: nothing to send.
  const blocked = length === 0 || !!askError || !!videoProblem;

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (blocked) {
      if (length === 0) askRef.current?.focus();
      return;
    }
    const form = new FormData(e.currentTarget);
    const video = form.get("video") as File | null;
    const url = String(form.get("url") ?? "").trim();
    const hasVideo = !!video && video.size > 0;
    form.set("request", ask.trim());
    if (!hasVideo && !url && !sourceJob) {
      setError("Add a video: upload a clip or paste a YouTube link.");
      return;
    }
    if (!hasVideo) form.delete("video");
    if (hasVideo || !url) form.delete("url");
    setStarting(form.has("url") ? "Checking the link..." : "Starting...");
    setProgress(0);
    setError(null);
    try {
      const job = await submitJob("coach", form, setProgress);
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError((err as Error).message);
      setProgress(null);
    }
  }

  return (
    <>
      <form onSubmit={onSubmit} noValidate className="coach-surface coach-form feature-form">
        <PageIntro
          eyebrow="TT Coach"
          title="Ask your coach."
          body="One request, one video. The coach finds your rallies and your best strokes, compares you with the pros, and shows each result as soon as it's ready."
        />
        <div className="coach-request">
          <div className="flex items-end justify-between">
            <label className={labelClass} htmlFor="request">What do you want?</label>
            <span aria-hidden className={`mb-2 text-xs tabular-nums ${askError ? "font-bold text-red-200" : "text-muted"}`}>
              {length}/{most}
            </span>
          </div>
          <textarea
            ref={askRef} id="request" name="request" rows={3} value={ask} onChange={(e) => setAsk(e.target.value)}
            aria-invalid={!!askError} aria-describedby="request-error"
            className={`${inputClass} ${askError ? "border-red-500/50" : ""}`}
            placeholder="e.g. Show my best rallies and fix my forehand"
          />
          <FieldError id="request-error">{askError}</FieldError>
          <div className="coach-prompts mt-3 grid gap-2">
            {EXAMPLES.map((x) => (
              <button
                key={x} type="button"
                onClick={() => { setAsk(x); askRef.current?.focus(); }}
                className="min-h-12 border px-3 py-2 text-left text-sm font-semibold"
              >
                {x}
              </button>
            ))}
          </div>
        </div>
        <div className="coach-upload">
          {sourceJob ? <MatchSource job={sourceJob} form="coach" /> : (
            <VideoPicker findPlayer onlyMeOption kind="coach" onProblem={setVideoProblem} title="Add your video" hint="A match or a practice clip, with the sound on." />
          )}
        </div>
        <SubmitBar
          label="Ask the coach" progress={progress} error={error} startingLabel={starting}
          blocked={blocked} blockedHint="Add a video or link to start"
        />
      </form>
      <div className="coach-surface coach-example"><CoachExample /></div>
    </>
  );
}
