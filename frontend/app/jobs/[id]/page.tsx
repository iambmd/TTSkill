"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import type { Job } from "@/lib/submit";
import { DownloadIcon, Warning, buttonBaseClass, secondaryButtonClass, strokeFamily } from "../../ui";
import { AutoCutWaiting } from "./autocut-waiting";
import { AnalysedPlayer } from "./analysed-player";
import { CoachView } from "./coach-view";
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
  // Hold the expected shape until metadata arrives, then switch to the clip's real one (a match filmed upright is vertical).
  const [ratio, setRatio] = useState<number | null>(null);
  return (
    <div
      className={`video-frame mx-auto overflow-hidden border ${vertical ? "sm:w-[min(100%,calc(78svh*9/16))] lg:w-full" : ""}`}
    >
      {job.resultUrl ? (
        <video
          key={job.resultUrl} src={`${job.resultUrl}#t=0.001`} controls playsInline preload="metadata"
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
    </div>
  );
}

function titleFor(job: Job) {
  if (job.breakdown) return job.breakdown.headline;
  if (job.status === "failed") return "Something went wrong";
  if (job.kind === "match" && job.matches?.length) return `You play like ${job.matches[0].name}`;
  if (job.status !== "done") {
    return job.kind === "breakdown" ? "Building your breakdown" : job.kind === "match" ? "Finding your pro match" : "Cutting your match";
  }
  if (job.kind === "autocut" && !job.rallies?.length && job.warning) return "No rallies found";
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

/** Shown when polls keep failing, so a lost server never looks like a job that is just slow. */
function Trouble({ text }: { text: string | null }) {
  if (!text) return null;
  return (
    <p role="alert" className="mx-auto mb-4 max-w-5xl rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
      {text}
    </p>
  );
}

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [trouble, setTrouble] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let alive = true;
    let failures = 0;
    async function poll() {
      try {
        const res = await fetch(`/api/jobs/${id}`, { cache: "no-store", signal: controller.signal });
        if (res.status >= 400 && res.status < 500 && res.status !== 408 && res.status !== 429) {
          const data = await res.json().catch(() => ({}));
          if (alive) setError(data.error ?? "Job not found");
          return;
        }
        // A 5xx or an HTML error page is a server problem, not the job's answer: retry.
        if (!res.ok) throw new Error(`server error ${res.status}`);
        const data = (await res.json()) as Job;
        if (!alive) return;
        failures = 0;
        setTrouble(null);
        setJob(data);
        if (data.status === "queued" || data.status === "running") timer = setTimeout(poll, 1500);
      } catch {
        if (!alive) return;
        failures += 1;
        if (failures >= 3) setTrouble("Can't reach the server right now. Still trying... If this stays, check that the backend is running.");
        timer = setTimeout(poll, Math.min(10_000, 1500 * 2 ** Math.min(failures, 3)));
      }
    }
    poll();
    return () => { alive = false; clearTimeout(timer); controller.abort(); };
  }, [id]);

  if (error) {
    return (
      <div className="mx-auto max-w-xl space-y-4 rounded-3xl border border-red-500/30 bg-red-500/10 p-6">
        <p className="section-title text-4xl">Job not found</p>
        <p className="text-red-200">{error}</p>
        <Link href="/" className={secondaryButtonClass}>Back home</Link>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="mx-auto max-w-3xl" aria-busy="true">
        <Trouble text={trouble} />
        <div className="stripes -mx-4 -mt-6 aspect-video bg-panel sm:mx-0 sm:mt-0 sm:rounded-3xl" />
        <p className="mt-4 text-muted">Loading...</p>
      </div>
    );
  }

  if (job.kind === "coach") return <><Trouble text={trouble} /><CoachView job={job} /></>;

  const vertical = job.kind !== "autocut";
  const ended = job.status === "done" || job.status === "failed";

  return (
    <>
    <Trouble text={trouble} />
    <div className={`mx-auto ${vertical ? "max-w-5xl lg:grid lg:grid-cols-[minmax(0,24rem)_minmax(0,1fr)] lg:items-start lg:gap-10" : "max-w-3xl"}`}>
      <div className={`min-w-0 ${vertical ? "lg:sticky lg:top-20" : ""}`}>
        {job.kind === "autocut" && !ended ? <AutoCutWaiting job={job} /> : <Stage job={job} />}
      </div>
      <div className="mt-6 min-w-0 space-y-8 lg:mt-0">
        <div className="space-y-3">
          <p className="eyebrow">{eyebrowFor(job)}</p>
          <h1 className="headline break-words text-5xl text-accent">{titleFor(job)}</h1>
          {job.message && (job.kind !== "autocut" || job.status === "queued") && <p className={job.status === "failed" ? "text-red-200" : "text-muted"}>{job.message}</p>}
          {job.warning && <Warning>{job.warning}</Warning>}
          {ended && (
            <div className="flex flex-wrap gap-2 pt-2">
              {job.resultUrl && (
                <a href={job.resultUrl} download={`ttskill-${job.id}.mp4`} className={`${buttonBaseClass} h-12 text-xl`}>
                  <DownloadIcon /> Download
                </a>
              )}
              <Link href={job.kind === "autocut" ? "/" : `/${job.kind}`} className={secondaryButtonClass}>
                {job.kind === "breakdown" ? "New breakdown" : job.kind === "match" ? "Match again" : "Cut another"}
              </Link>
            </div>
          )}
        </div>
        <AnalysedPlayer job={job} />
        {job.breakdown && <Steps b={job.breakdown} />}
        {job.matches && job.matches.length > 0 && <Matches matches={job.matches} stroke={str(job.params.stroke)} />}
        {job.status === "done" && job.rallies && job.rallies.length > 0 && <Rallies rallies={job.rallies} full={job.params.mode === "full"} />}
        {job.kind === "autocut" && job.status === "done" && job.canReuseVideo && <GoDeeper id={job.id} />}
        {job.kind !== "autocut" && <details className="group surface-card">
          <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3.5 text-sm font-semibold text-muted [&::-webkit-details-marker]:hidden">
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
