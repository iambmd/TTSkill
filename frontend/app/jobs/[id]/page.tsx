"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import type { Breakdown, Job } from "@/lib/submit";
import { DownloadIcon, buttonBaseClass, secondaryButtonClass } from "../../ui";

type Rally = NonNullable<Job["rallies"]>[number];

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const STATUS: Record<Job["status"], string> = { queued: "In the queue", running: "Processing", done: "Done", failed: "Failed" };
const str = (v: unknown) => (typeof v === "string" && v ? v : undefined);

/** The video, or a same-shaped placeholder while the job runs. Breakdowns are vertical, match cuts landscape. */
function Stage({ job }: { job: Job }) {
  const vertical = job.kind === "breakdown";
  const pct = Math.round(job.progress * 100);
  const failed = job.status === "failed";
  // Hold the expected shape until metadata arrives, then switch to the clip's real one (a match filmed upright is vertical).
  const [ratio, setRatio] = useState<number | null>(null);
  return (
    <div
      className={`-mx-4 -mt-6 overflow-hidden bg-black sm:mx-auto sm:mt-0 sm:rounded-3xl sm:border sm:border-line ${vertical ? "sm:w-[min(100%,calc(78svh*9/16))] lg:w-full" : ""}`}
    >
      {job.resultUrl ? (
        <video
          key={job.resultUrl} src={`${job.resultUrl}#t=0.001`} controls playsInline preload="metadata"
          onLoadedMetadata={(e) => {
            const v = e.currentTarget;
            if (v.videoWidth && v.videoHeight) setRatio(v.videoWidth / v.videoHeight);
          }}
          style={{ aspectRatio: ratio ?? (vertical ? 9 / 16 : 16 / 9) }}
          className="mx-auto block max-h-[78svh] w-full bg-black object-contain"
        />
      ) : (
        <div
          className={`relative flex flex-col items-center justify-center gap-2 px-6 text-center ${vertical ? "aspect-[9/16] max-h-[70svh] w-full sm:max-h-none" : "aspect-video"} ${failed ? "bg-red-500/10" : "stripes"}`}
        >
          {failed ? (
            <span className="headline text-5xl text-red-300">Failed</span>
          ) : job.status === "done" ? (
            <span className="headline text-5xl">No video</span>
          ) : (
            <span className="headline text-8xl tabular-nums">
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
  if (job.status !== "done") return job.kind === "breakdown" ? "Building your breakdown" : "Cutting your match";
  if (job.kind === "autocut" && job.rallies?.length) {
    return job.params.mode === "full" ? `All ${job.rallies.length} rallies` : `Top ${job.rallies.length} rallies`;
  }
  return "All done";
}

function eyebrowFor(job: Job) {
  if (job.kind === "breakdown") {
    const player = job.breakdown?.player ?? str(job.params.player);
    const st = job.strokeType;
    const stroke = st ? `${st.label}${st.detected ? " (auto-detected)" : ""}` : job.breakdown?.stroke ?? str(job.params.stroke);
    return ["Technique breakdown", player, stroke].filter(Boolean).join(" · ");
  }
  return `Match Auto-Cut · ${job.params.mode === "full" ? "Full match" : "Highlights"}`;
}

function Steps({ b }: { b: Breakdown }) {
  const facts: [string, string][] = [
    ["Grip", b.grip], ["Stance", b.stance], ["Swing path", b.swing_path],
    ["Contact point", b.contact_point], ["Follow-through", b.follow_through],
  ];
  return (
    <>
      <section className="space-y-3">
        <h2 className="eyebrow">Step by step</h2>
        <ol className="space-y-2">
          {b.steps.map((s, i) => (
            <li key={i} className="flex gap-4 rounded-2xl border border-line bg-panel p-4">
              <span className="headline text-4xl leading-none text-accent">{String(i + 1).padStart(2, "0")}</span>
              <div className="min-w-0 space-y-1">
                <p className="text-lg font-bold">{s.title}</p>
                {s.lines.map((l) => <p key={l} className="text-muted">{l}</p>)}
                {s.callouts?.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {s.callouts.map((c) => (
                      <span key={c} className="rounded-md bg-accent/15 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-accent">{c}</span>
                    ))}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
        {b.recap && <p className="headline text-2xl text-muted">{b.recap}</p>}
      </section>
      {b.drill && (
        <section className="rounded-2xl border border-accent/40 bg-accent/10 p-4">
          <h2 className="eyebrow">Try this</h2>
          <p className="mt-1 text-lg font-semibold">{b.drill}</p>
        </section>
      )}
      <section className="space-y-3">
        <h2 className="eyebrow">The details</h2>
        <dl className="divide-y divide-line rounded-2xl border border-line bg-panel">
          {facts.map(([k, v]) => (
            <div key={k} className="grid gap-1 px-4 py-3 sm:grid-cols-[9rem_1fr] sm:gap-4">
              <dt className="text-xs font-bold uppercase tracking-widest text-muted sm:pt-0.5">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </section>
    </>
  );
}

function Rallies({ rallies, full }: { rallies: Rally[]; full: boolean }) {
  const most = Math.max(1, ...rallies.map((r) => r.shots));
  const total = rallies.reduce((t, r) => t + r.end - r.start, 0);
  const stats: [string, string | number][] = [["Rallies", rallies.length], ["Most shots", most], ["Rally time", fmt(total)]];
  return (
    <section className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        {stats.map(([k, v]) => (
          <div key={k} className="rounded-2xl border border-line bg-panel px-3 py-3 text-center">
            <p className="headline text-4xl tabular-nums">{v}</p>
            <p className="mt-1 text-[0.65rem] font-bold uppercase tracking-widest text-muted">{k}</p>
          </div>
        ))}
      </div>
      <h2 className="eyebrow pt-3">{full ? "Every rally, in order" : "Best rallies, most shots first"}</h2>
      <ol className="space-y-2">
        {rallies.map((r, i) => (
          <li key={i} className="relative overflow-hidden rounded-xl border border-line bg-panel px-4 py-3">
            <div aria-hidden className="absolute inset-y-0 left-0 bg-accent/10" style={{ width: `${(r.shots / most) * 100}%` }} />
            <div className="relative flex items-center gap-4">
              <span className="headline w-7 text-2xl text-muted">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold tabular-nums">{fmt(r.start)} – {fmt(r.end)}</p>
                <p className="text-xs text-muted">{Math.round(r.end - r.start)} s, match time</p>
              </div>
              <p className="shrink-0">
                <span className="headline text-3xl text-accent tabular-nums">{r.shots}</span>
                <span className="ml-1 text-xs font-bold uppercase text-muted">shots</span>
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let alive = true;
    async function poll() {
      try {
        const res = await fetch(`/api/jobs/${id}`, { cache: "no-store" });
        const data = await res.json();
        if (!alive) return;
        if (!res.ok) return setError(data.error ?? "Job not found");
        setJob(data);
        if (data.status === "queued" || data.status === "running") timer = setTimeout(poll, 1500);
      } catch {
        // Network blip: keep polling instead of freezing on the last state.
        if (alive) timer = setTimeout(poll, 3000);
      }
    }
    poll();
    return () => { alive = false; clearTimeout(timer); };
  }, [id]);

  if (error) {
    return (
      <div className="mx-auto max-w-xl space-y-4 rounded-3xl border border-red-500/30 bg-red-500/10 p-6">
        <p className="headline text-4xl">Job not found</p>
        <p className="text-red-200">{error}</p>
        <Link href="/" className={secondaryButtonClass}>Back home</Link>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="mx-auto max-w-3xl" aria-busy="true">
        <div className="stripes -mx-4 -mt-6 aspect-video bg-panel sm:mx-0 sm:mt-0 sm:rounded-3xl" />
        <p className="mt-4 text-muted">Loading...</p>
      </div>
    );
  }

  const vertical = job.kind === "breakdown";
  const ended = job.status === "done" || job.status === "failed";

  return (
    <div className={`mx-auto ${vertical ? "max-w-5xl lg:grid lg:grid-cols-[minmax(0,24rem)_1fr] lg:items-start lg:gap-10" : "max-w-3xl"}`}>
      <div className={vertical ? "lg:sticky lg:top-20" : ""}>
        <Stage job={job} />
      </div>
      <div className="mt-6 space-y-8 lg:mt-0">
        <div className="space-y-3">
          <p className="eyebrow">{eyebrowFor(job)}</p>
          <h1 className="headline text-5xl">{titleFor(job)}</h1>
          {job.message && <p className={job.status === "failed" ? "text-red-200" : "text-muted"}>{job.message}</p>}
          {ended && (
            <div className="grid grid-cols-2 gap-2 pt-2 sm:flex">
              {job.resultUrl && (
                <a href={job.resultUrl} download={`ttskill-${job.id}.mp4`} className={`${buttonBaseClass} h-12 text-xl`}>
                  <DownloadIcon /> Download
                </a>
              )}
              <Link href={`/${job.kind}`} className={secondaryButtonClass}>
                {job.kind === "breakdown" ? "New breakdown" : "Cut another"}
              </Link>
            </div>
          )}
        </div>
        {job.breakdown && <Steps b={job.breakdown} />}
        {job.rallies && job.rallies.length > 0 && <Rallies rallies={job.rallies} full={job.params.mode === "full"} />}
        <details className="group rounded-2xl border border-line bg-panel">
          <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3.5 text-sm font-semibold text-muted [&::-webkit-details-marker]:hidden">
            Run details
            <span aria-hidden className="transition group-open:rotate-45">+</span>
          </summary>
          <pre className="overflow-x-auto px-4 pb-4 text-xs text-muted">{JSON.stringify(job.params, null, 2)}</pre>
        </details>
      </div>
    </div>
  );
}
