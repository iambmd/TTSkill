"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { OfflineNotice } from "../../offline-notice";
import { demoDescriptions } from "@/lib/demo-descriptions";
import type { Job } from "@/lib/submit";
import { DownloadIcon, Warning, buttonBaseClass, secondaryButtonClass, strokeFamily } from "../../ui";
import { AutoCutWaiting } from "./autocut-waiting";
import { AnalysedPlayer } from "./analysed-player";
import { CoachView } from "./coach-view";
import { RallyEditor } from "./rally-editor";
import { Matches } from "./matches";
import { Steps } from "./steps";

type Rally = NonNullable<Job["rallies"]>[number];

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const STATUS: Record<Job["status"], string> = { queued: "In the queue", running: "Processing", done: "Done", failed: "Failed" };
const str = (v: unknown) => (typeof v === "string" && v ? v : undefined);

/** The video, or a same-shaped placeholder while the job runs. Breakdowns are vertical, match cuts landscape. */
function Stage({ job }: { job: Job }) {
  const vertical = job.kind !== "autocut";
  const pct = Math.round(job.progress * 100);
  const failed = job.status === "failed";
  const description = job.kind !== "coach" && job.id === `demo-${job.kind}` ? demoDescriptions[job.kind] : null;
  // Hold the expected shape until metadata arrives, then switch to the clip's real one (a match filmed upright is vertical).
  const [ratio, setRatio] = useState<number | null>(null);
  return (
    <figure
      className={`video-frame mx-auto overflow-hidden border ${vertical ? "sm:w-[min(100%,calc(78svh*9/16))] lg:w-full" : ""}`}
    >
      {job.resultUrl ? (
        <video
          key={job.resultUrl} src={`${job.resultUrl}#t=0.001`} controls playsInline preload="metadata"
          aria-label={job.kind === "autocut" ? "Match highlight reel" : job.kind === "match" ? "Pro match video" : "Technique breakdown video"}
          aria-describedby={description ? "result-description" : undefined}
          onLoadedMetadata={(e) => {
            const v = e.currentTarget;
            if (v.videoWidth && v.videoHeight) setRatio(v.videoWidth / v.videoHeight);
          }}
          style={{ aspectRatio: ratio ?? (vertical ? 9 / 16 : 16 / 9) }}
          className="mx-auto block max-h-[78svh] w-full object-contain"
        />
      ) : (
        <div
          className={`relative flex flex-col items-center justify-center gap-2 bg-panel px-6 text-center ${vertical ? "aspect-[9/16] max-h-[70svh] w-full sm:max-h-none" : "aspect-video"} ${failed ? "bg-red-500/10" : "stripes"}`}
        >
          {failed ? (
            <span className="section-title text-4xl text-red-300">Failed</span>
          ) : job.status === "done" ? (
            <span className="section-title text-4xl">No video</span>
          ) : (
            <span className="font-bold leading-none text-7xl tabular-nums">
              {pct}<span className="text-4xl text-accent">%</span>
            </span>
          )}
          <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-muted">
            {!failed && job.status !== "done" && <span className="size-2 animate-pulse rounded-full bg-accent" />}
            {STATUS[job.status]}
          </span>
          {!failed && (
            <div
              role="progressbar" aria-label="Job progress" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}
              className="absolute inset-x-0 bottom-0 h-1.5 bg-white/10"
            >
              <div className="h-full bg-accent transition-[width] duration-500" style={{ width: `${pct}%` }} />
            </div>
          )}
        </div>
      )}
      {job.resultUrl && description && <figcaption id="result-description" className="bg-panel p-3 text-sm text-muted">{description}</figcaption>}
    </figure>
  );
}

function titleFor(job: Job) {
  if (job.breakdown) return job.breakdown.headline;
  if (job.status === "failed") return "Something went wrong";
  if (job.kind === "match" && job.matches?.length) return `You play like ${job.matches[0].name}`;
  if (job.status !== "done") {
    return job.kind === "breakdown" ? "Building your breakdown" : job.kind === "match" ? "Finding your pro match" : "Cutting your match";
  }
  if (job.kind === "autocut" && !job.resultUrl) return "No rallies found";
  if (job.kind === "autocut" && job.rallies?.length) {
    return job.params.mode === "full" ? `All ${job.rallies.length} rallies` : `Top ${job.rallies.length} rallies`;
  }
  return "All done";
}

function strokeLabel(text: string, key = text) {
  const family = strokeFamily(key);
  return family ? <span className="stroke-label" data-stroke={family}>{text}</span> : text;
}

function eyebrowFor(job: Job) {
  if (job.kind === "breakdown") {
    const player = job.breakdown?.player ?? str(job.params.player);
    const st = job.strokeType;
    const stroke = st ? `${st.label}${st.detected ? " (auto-detected)" : ""}` : job.breakdown?.stroke ?? str(job.params.stroke);
    return <>{["Technique breakdown", player].filter(Boolean).join(" · ")}{stroke && <> · {strokeLabel(stroke, st?.key ?? job.breakdown?.stroke_type ?? stroke)}</>}</>;
  }
  if (job.kind === "match") {
    const h = job.you?.height;
    const height = h ? `${h.height_cm} cm${h.method === "entered" ? "" : " (from the table)"}` : undefined;
    const stroke = str(job.params.stroke);
    return <>Find my pro match{stroke && <> · {strokeLabel(stroke)}</>}{height && <> · {height}</>}</>;
  }
  return `Match Auto-Cut · ${job.params.mode === "full" ? "Full match" : "Highlights"}`;
}

function Rallies({ rallies, full }: { rallies: Rally[]; full: boolean }) {
  return (
    <section className="space-y-3">
      <h2 className="eyebrow">{full ? "Every rally" : "Highlights"}</h2>
      <ol className="space-y-2">
        {rallies.map((r, i) => (
          <li key={i} className="surface-card flex items-center gap-4 px-4 py-3">
            <span className="font-bold">Rally {i + 1}</span>
            <span className="text-sm text-muted">{fmt(r.start)} – {fmt(r.end)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function GoDeeper({ id }: { id: string }) {
  return (
    <section aria-labelledby="deeper-title" className="space-y-3">
      <h2 id="deeper-title" className="section-title text-2xl">Go deeper</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {([
          ["coach", "Coach this match", "Ask what to work on in the match you uploaded."],
          ["breakdown", "Break down a stroke", "Get a step-by-step look at a stroke from this video."],
        ] as const).map(([path, title, body]) => (
          <Link key={path} href={`/${path}?source=${id}`} className="surface-card space-y-1 p-4 hover:border-accent">
            <h3 className="font-bold text-accent">{title}</h3>
            <p className="text-sm text-muted">{body}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}

function JobFailure({ job }: { job: Job }) {
  return (
    <div className="surface-card space-y-3 p-4">
      <p role="alert" className="text-red-200">
        {job.failureHint ?? "We couldn't finish this analysis. Try again or upload a shorter clip."}
      </p>
      <Link href={job.kind === "autocut" ? "/" : `/${job.kind}`} className={secondaryButtonClass}>
        Try another recording
      </Link>
    </div>
  );
}

function NoRallies() {
  return (
    <div role="status" className="surface-card p-4 text-muted">
      Try filming closer to the table in a quieter spot, with both players in frame.
    </div>
  );
}

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let request: AbortController | undefined;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      request = new AbortController();
      const controller = request;
      const deadline = setTimeout(() => controller.abort(), 10_000);
      try {
        const res = await fetch(`/api/jobs/${id}`, { cache: "no-store", signal: controller.signal });
        if (cancelled) return;
        if (res.status === 404) {
          setError("Open the match result again or upload a new video.");
          return;
        }
        if (!res.ok) throw new Error("The job isn't reachable.");
        const next = (await res.json()) as Job;
        if (cancelled) return;
        if (next.id !== id || !["queued", "running", "done", "failed"].includes(next.status)) {
          throw new Error("The server didn't send a job.");
        }
        setOffline(false);
        setRetrying(false);
        setJob(next);
        if (next.status === "queued" || next.status === "running") timer = setTimeout(poll, 1500);
      } catch {
        if (cancelled) return;
        setOffline(true);
        setRetrying(false);
      } finally {
        clearTimeout(deadline);
      }
    }
    void poll();
    return () => { cancelled = true; clearTimeout(timer); request?.abort(); };
  }, [id, attempt]);

  const offlineNotice = offline && <OfflineNotice checking={retrying} onRetry={() => {
    setRetrying(true);
    setAttempt((n) => n + 1);
  }} />;

  if (error) {
    return (
      <div className="mx-auto max-w-xl space-y-4 rounded-3xl border border-red-500/30 bg-red-500/10 p-6">
        <h1 className="section-title text-4xl">Job not found</h1>
        <p role="alert" className="text-red-200">{error}</p>
        <Link href="/" className={secondaryButtonClass}>Back home</Link>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        {offlineNotice || <p role="status" className="surface-card p-4 text-muted">Loading your result…</p>}
      </div>
    );
  }

  const failed = job.status === "failed";
  if (job.kind === "coach") return (
    <div className="space-y-4">
      {offlineNotice}
      {failed && <JobFailure job={job} />}
      <CoachView job={job} />
    </div>
  );

  const vertical = job.kind !== "autocut" && !failed;
  const ended = job.status === "done" || job.status === "failed";

  return (
    <>
    <p role="status" className="sr-only">{job.status === "done" ? (job.kind === "autocut" && !job.resultUrl ? "No rallies found." : "Your result is ready.") : ""}</p>
    {offlineNotice && <div className="mx-auto mb-4 max-w-3xl">{offlineNotice}</div>}
    <div className={`mx-auto ${vertical ? "max-w-5xl lg:grid lg:grid-cols-[minmax(0,24rem)_minmax(0,1fr)] lg:items-start lg:gap-10" : "max-w-3xl"}`}>
      {(!ended || job.resultUrl) && (
        <div className={`min-w-0 ${vertical ? "lg:sticky lg:top-20" : ""}`}>
          {job.kind === "autocut" && !ended ? <AutoCutWaiting job={job} /> : <Stage job={job} />}
        </div>
      )}
      <div className="mt-6 min-w-0 space-y-8 lg:mt-0">
        <div className="space-y-3">
          <p className="eyebrow">{eyebrowFor(job)}</p>
          <h1 className="headline break-words text-5xl text-accent">{titleFor(job)}</h1>
          {!failed && (job.kind !== "autocut" || job.status === "queued") && <p role={ended ? undefined : "status"} className="text-muted">{job.message}</p>}
          {failed && <JobFailure job={job} />}
          {job.kind === "autocut" && job.status === "done" && !job.resultUrl && <NoRallies />}
          {job.warning && (job.kind !== "autocut" || job.resultUrl) && <Warning>{job.warning}</Warning>}
          {job.status === "done" && (
            <div className="flex flex-wrap gap-2 pt-2">
              {job.resultUrl && !job.rallyClips?.length && (
                <a href={job.resultUrl} download={`ttskill-${job.id}.mp4`} className={`${buttonBaseClass} h-12 text-xl`}>
                  <DownloadIcon /> Download
                </a>
              )}
              <Link href={job.kind === "autocut" ? "/" : `/${job.kind}`} className={secondaryButtonClass}>
                {job.kind === "breakdown" ? "New breakdown" : job.kind === "match" ? "Match again" : job.resultUrl ? "Cut another" : "Try another recording"}
              </Link>
            </div>
          )}
        </div>
        <AnalysedPlayer job={job} />
        {job.breakdown && <Steps b={job.breakdown} />}
        {job.matches && job.matches.length > 0 && <Matches matches={job.matches} stroke={str(job.params.stroke)} />}
        {job.status === "done" && (job.rallyClips?.length
          ? <RallyEditor key={job.id} id={job.id} clips={job.rallyClips} />
          : !!job.rallies?.length && <Rallies rallies={job.rallies} full={job.params.mode === "full"} />)}
        {job.kind === "autocut" && job.status === "done" && job.canReuseVideo && <GoDeeper id={job.id} />}
        {job.kind !== "autocut" && <details className="group surface-card">
          <summary className="flex list-none items-center justify-between px-4 py-3.5 text-sm font-semibold text-muted [&::-webkit-details-marker]:hidden">
            Run details
            <span aria-hidden className="transition group-open:rotate-45">+</span>
          </summary>
          <pre className="overflow-x-auto whitespace-pre-wrap break-all px-4 pb-4 text-xs text-muted">{JSON.stringify(job.params, null, 2)}</pre>
        </details>}
      </div>
    </div>
    </>
  );
}
