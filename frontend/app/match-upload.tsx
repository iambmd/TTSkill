"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AnalysisOfflineError, checkAnalysisHealth } from "@/lib/analysis-status";
import { submitJob } from "@/lib/submit";
import { fileProblem, LIMITS } from "@/lib/validate";
import { FieldError, secondaryButtonClass, UploadIcon } from "./ui";
import { OfflineNotice } from "./offline-notice";

export function MatchUpload() {
  const router = useRouter();
  const uploading = useRef(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const [offline, setOffline] = useState(false);
  const [checking, setChecking] = useState(true);
  const [healthAttempt, setHealthAttempt] = useState(0);
  const [retryFile, setRetryFile] = useState<File | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    checkAnalysisHealth(controller.signal).then((healthy) => {
      if (controller.signal.aborted) return;
      setOffline(!healthy);
      setChecking(false);
    });
    return () => controller.abort();
  }, [healthAttempt]);

  async function upload(file?: File) {
    if (!file || uploading.current || offline) return;
    setRetryFile(null);
    const problem = !/\.(mp4|mov)$/i.test(file.name) ? "Choose an MP4 or MOV video."
      : !file.size ? "That file is empty. Choose another recording." : fileProblem(file);
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
      setRetryFile(file);
      if (err instanceof AnalysisOfflineError || !(await checkAnalysisHealth())) {
        setOffline(true);
      } else {
        setError((err as Error).message);
      }
      setProgress(null);
      uploading.current = false;
    }
  }

  const busy = progress !== null;
  const percent = Math.round((progress ?? 0) * 100);
  return (
    <div className="space-y-3">
      {offline && <OfflineNotice checking={checking} onRetry={() => {
        setChecking(true);
        setHealthAttempt((n) => n + 1);
      }} />}
      <label
        className={`video-picker block rounded-[var(--training-panel-radius)] has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-4 has-[:focus-visible]:outline-accent ${dragging ? "ring-2 ring-accent" : ""}`}
        onDragOver={(e) => { e.preventDefault(); if (!busy && !offline) setDragging(true); }}
        onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false); }}
        onDrop={(e) => { e.preventDefault(); setDragging(false); void upload(e.dataTransfer.files[0]); }}
      >
        <input
          type="file" accept=".mp4,.mov,video/mp4,video/quicktime" disabled={busy || offline}
          aria-label="Choose a video or drop it here"
          aria-describedby={error ? "match-upload-error" : "match-upload-hint"}
          className="sr-only"
          onChange={(e) => { void upload(e.target.files?.[0]); e.target.value = ""; }}
        />
        <span className={`upload-target match-dropzone flex flex-col items-center justify-center text-center ${busy ? "cursor-wait" : offline ? "cursor-not-allowed" : "cursor-pointer"}`}>
          <span className="grid place-items-center"><UploadIcon /></span>
          <span className="section-title text-2xl" aria-live="polite">
            {busy ? percent === 100 ? "Starting your reel…" : `Uploading ${percent}%` : "Choose a video or drop it here"}
          </span>
          <span id="match-upload-hint" className="text-sm">MP4 or MOV · Up to {LIMITS.upload.max_mb} MB</span>
        </span>
      </label>
      {busy && <progress className="h-2 w-full accent-accent" value={percent} max={100} aria-label="Upload progress" />}
      <FieldError id="match-upload-error">{error}</FieldError>
      {!busy && !offline && retryFile && (
        <button type="button" className={secondaryButtonClass} onClick={() => void upload(retryFile)}>
          Retry upload
        </button>
      )}
    </div>
  );
}
