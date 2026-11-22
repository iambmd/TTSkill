"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { submitJob } from "@/lib/submit";
import { fileProblem, LIMITS } from "@/lib/validate";
import { FieldError, UploadIcon } from "./ui";

export function MatchUpload() {
  const router = useRouter();
  const uploading = useRef(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  async function upload(file?: File) {
    if (!file || uploading.current) return;
    const problem = /\.(mp4|mov)$/i.test(file.name) ? fileProblem(file) : "Choose an MP4 or MOV video.";
    setError(problem);
    if (problem) return;
    uploading.current = true;
    setProgress(0);
    const form = new FormData();
    form.set("video", file);
    form.set("mode", "highlights");
    try {
      const job = await submitJob("autocut", form, setProgress);
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError((err as Error).message);
      setProgress(null);
      uploading.current = false;
    }
  }

  const busy = progress !== null;
  const percent = Math.round((progress ?? 0) * 100);
  return (
    <div className="space-y-3">
      <label
        className={`video-picker block rounded-[var(--training-panel-radius)] has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-4 has-[:focus-visible]:outline-accent ${dragging ? "ring-2 ring-accent" : ""}`}
        onDragOver={(e) => { e.preventDefault(); if (!busy) setDragging(true); }}
        onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false); }}
        onDrop={(e) => { e.preventDefault(); setDragging(false); void upload(e.dataTransfer.files[0]); }}
      >
        <input
          type="file" accept=".mp4,.mov,video/mp4,video/quicktime" disabled={busy}
          aria-label="Choose an MP4 or MOV match video"
          aria-describedby={error ? "match-upload-error" : "match-upload-hint"}
          className="sr-only"
          onChange={(e) => { void upload(e.target.files?.[0]); e.target.value = ""; }}
        />
        <span className={`upload-target match-dropzone flex flex-col items-center justify-center text-center ${busy ? "cursor-wait" : "cursor-pointer"}`}>
          <span className="grid place-items-center"><UploadIcon /></span>
          <span className="section-title text-2xl" aria-live="polite">
            {busy ? percent === 100 ? "Starting your reel…" : `Uploading ${percent}%` : "Choose a video or drop it here"}
          </span>
          <span id="match-upload-hint" className="text-sm">MP4 or MOV · Up to {LIMITS.upload.max_mb} MB</span>
        </span>
      </label>
      {busy && <progress className="h-2 w-full accent-accent" value={percent} max={100} aria-label="Upload progress" />}
      <FieldError id="match-upload-error">{error}</FieldError>
    </div>
  );
}
