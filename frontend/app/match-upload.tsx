"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { AnalysisOfflineError, checkAnalysisHealth } from "@/lib/analysis-status";
import { submitJob } from "@/lib/submit";
import { fileProblem, LIMITS } from "@/lib/validate";
import { FieldError, secondaryButtonClass, UploadIcon } from "./ui";
import { OfflineNotice } from "./offline-notice";

export function MatchUpload() {
  const t = useTranslations("home.upload");
  const tAll = useTranslations();
  const tv = useTranslations("validation");
  const router = useRouter();
  const uploading = useRef(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const [offline, setOffline] = useState(false);
  const [checking, setChecking] = useState(true);
  const [healthAttempt, setHealthAttempt] = useState(0);
  const [retryFile, setRetryFile] = useState<File | null>(null);
  const pickerRef = useRef<HTMLInputElement>(null);
  const focusAfterRetry = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    checkAnalysisHealth(controller.signal).then((healthy) => {
      if (controller.signal.aborted) return;
      setOffline(!healthy);
      setChecking(false);
    });
    return () => controller.abort();
  }, [healthAttempt]);

  useEffect(() => {
    if (!offline && !checking && focusAfterRetry.current) {
      focusAfterRetry.current = false;
      pickerRef.current?.focus();
    }
  }, [offline, checking]);

  async function upload(file?: File) {
    if (!file || uploading.current || offline) return;
    setRetryFile(null);
    const problem = !/\.(mp4|mov)$/i.test(file.name) ? t("chooseType")
      : !file.size ? t("empty") : fileProblem(file, tv);
    setError(problem);
    if (problem) return;
    uploading.current = true;
    setProgress(0);
    const form = new FormData();
    form.set("video", file);
    form.set("mode", "highlights");
    try {
      const job = await submitJob("autocut", form, setProgress, tAll);
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
  if (offline) {
    return <div className="home-upload-offline">
      <OfflineNotice checking={checking} message={tAll("offline.home")} onRetry={() => {
        focusAfterRetry.current = true;
        setChecking(true);
        setHealthAttempt((n) => n + 1);
      }} />
    </div>;
  }

  return (
    <div className="space-y-3">
      <label
        className={`video-picker block rounded-[var(--training-panel-radius)] has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-4 has-[:focus-visible]:outline-accent ${dragging ? "ring-2 ring-accent" : ""}`}
        onDragOver={(e) => { e.preventDefault(); if (!busy) setDragging(true); }}
        onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false); }}
        onDrop={(e) => { e.preventDefault(); setDragging(false); void upload(e.dataTransfer.files[0]); }}
      >
        <input
          ref={pickerRef} type="file" accept=".mp4,.mov,video/mp4,video/quicktime" disabled={busy}
          aria-label={t("label")}
          aria-describedby={error ? "match-upload-error" : "match-upload-hint"}
          className="sr-only"
          onChange={(e) => { void upload(e.target.files?.[0]); e.target.value = ""; }}
        />
        <span className={`upload-target match-dropzone flex flex-col items-center justify-center text-center ${busy ? "cursor-wait" : ""}`}>
          <span className="grid place-items-center"><UploadIcon /></span>
          <span className="section-title text-2xl" aria-live="polite">
            {busy ? percent === 100 ? t("startingReel") : tAll("common.uploadingPct", { pct: percent }) : t("label")}
          </span>
          <span id="match-upload-hint" className="text-sm text-muted">{t("hint", { mb: LIMITS.upload.max_mb })}</span>
        </span>
      </label>
      {busy && <progress className="h-2 w-full accent-accent" value={percent} max={100} aria-label={t("progress")} />}
      <FieldError id="match-upload-error">{error}</FieldError>
      {!busy && retryFile && (
        <button type="button" className={secondaryButtonClass} onClick={() => void upload(retryFile)}>
          {t("retry")}
        </button>
      )}
    </div>
  );
}
