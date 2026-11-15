"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { submitJob } from "@/lib/submit";
import { LINK_HINT, youtubeId } from "@/lib/youtube";
import { PageIntro, SubmitBar, inputClass, labelClass } from "../ui";
import { VideoPicker } from "../video-picker";

const EXAMPLES = [
  "Here's my match: show my best rallies and fix my forehand",
  "Which pros do I play like? Compare my backhand",
  "Cut the dead time and tell me what to work on",
];

export default function CoachPage() {
  const router = useRouter();
  const askRef = useRef<HTMLTextAreaElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [starting, setStarting] = useState("Starting...");

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const video = form.get("video") as File | null;
    const url = String(form.get("url") ?? "").trim();
    const hasVideo = !!video && video.size > 0;
    if (!String(form.get("request") ?? "").trim()) {
      setError("Tell the coach what you want.");
      askRef.current?.focus();
      return;
    }
    if (!hasVideo && !url) {
      setError("Add a video: upload a clip or paste a YouTube link.");
      return;
    }
    if (!hasVideo && !youtubeId(url)) {
      setError(LINK_HINT);
      return;
    }
    if (!hasVideo) form.delete("video");
    if (hasVideo || !url) form.delete("url");
    setStarting(form.has("url") ? "Checking the link..." : "Starting...");
    setProgress(0);
    setError(null);
    try {
      const job = await submitJob("/api/jobs/coach", form, setProgress);
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError((err as Error).message);
      setProgress(null);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto max-w-xl space-y-7">
      <PageIntro
        eyebrow="TT Coach"
        title="Ask your coach."
        body="One request, one video. The coach plans the work, runs the tools, and shows you its to-do list as it goes."
      />
      <div>
        <label className={labelClass} htmlFor="request">What do you want?</label>
        <textarea
          ref={askRef} id="request" name="request" rows={3} className={inputClass}
          placeholder="e.g. Show my best rallies and fix my forehand"
        />
        <div className="mt-2 flex flex-wrap gap-2">
          {EXAMPLES.map((x) => (
            <button
              key={x} type="button"
              onClick={() => { if (askRef.current) { askRef.current.value = x; askRef.current.focus(); } }}
              className="rounded-full border border-line px-3 py-1.5 text-left text-xs font-semibold text-muted hover:border-accent hover:text-white"
            >
              {x}
            </button>
          ))}
        </div>
      </div>
      <VideoPicker title="Add your video" hint="A match or a practice clip, with the sound on." />
      <SubmitBar label="Ask the coach" progress={progress} error={error} startingLabel={starting} />
    </form>
  );
}
