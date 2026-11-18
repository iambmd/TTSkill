/** The TT Coach result page: the request and the plan on the left (stacked on phones), the
 * coaching notes first on the right, then the videos, the breakdown and the pro matches.
 *
 * Every grid and flex child that holds text has min-width 0 (`minmax(0, ...)` tracks): a grid
 * track sized `1fr` can't shrink below its widest content, so one unbroken line (the raw JSON
 * files this page used to show) pushed the right column wider than the page and squeezed the
 * plan to a word per line. */
import Link from "next/link";
import { coachingOf } from "@/lib/coaching";
import type { CoachNotes, Job } from "@/lib/submit";
import { Markdown } from "../../markdown";
import { CheckIcon, DownloadIcon, Warning, secondaryButtonClass } from "../../ui";
import { AnalysedPlayer } from "./analysed-player";
import { Matches } from "./matches";
import { Steps } from "./steps";

type Todo = NonNullable<Job["todos"]>[number];

const str = (v: unknown) => (typeof v === "string" && v ? v : undefined);
const isRunning = (job: Job) => job.status === "queued" || job.status === "running";
// The coach's working files are for us, not for players: only `next dev` shows them.
const DEV = process.env.NODE_ENV === "development";

function StepIcon({ status, stopped }: { status: Todo["status"]; stopped: boolean }) {
  if (status === "completed") {
    return <span className="grid size-5 shrink-0 place-items-center rounded-full bg-accent text-black"><CheckIcon className="size-3" /></span>;
  }
  if (status === "in_progress") {
    return stopped ? (
      <span className="grid size-5 shrink-0 place-items-center rounded-full border-2 border-red-400 text-[0.6rem] font-black text-red-400">!</span>
    ) : (
      <span className="grid size-5 shrink-0 place-items-center rounded-full border-2 border-accent"><span className="size-1.5 animate-pulse rounded-full bg-accent" /></span>
    );
  }
  return <span className="size-5 shrink-0 rounded-full border-2 border-white/15" />;
}

function StepList({ todos, stopped }: { todos: Todo[]; stopped: boolean }) {
  return (
    <ol className="space-y-0.5" aria-live="polite">
      {todos.map((t, i) => (
        <li key={i} className={`flex items-start gap-2.5 rounded-lg px-1.5 py-1 text-sm ${t.status === "in_progress" ? "bg-accent/10 font-semibold" : ""}`}>
          <StepIcon status={t.status} stopped={stopped} />
          <span className={`min-w-0 flex-1 [overflow-wrap:anywhere] ${t.status === "completed" ? "text-muted" : ""}`}>
            {t.content}
            {stopped && t.status === "in_progress" && <span className="font-normal text-red-300"> (stopped here)</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}

/** While the job runs: a compact checklist with a progress bar. Done: one "All steps done" line
 * that opens to the list. Failed: the list, showing where it stopped. */
export function Plan({ job }: { job: Job }) {
  const todos = job.todos ?? [];
  const running = isRunning(job);
  const failed = job.status === "failed";
  if (!todos.length) {
    return (
      <div className={`${running ? "stripes" : ""} rounded-2xl border border-line bg-panel p-4 text-sm text-muted`}>
        {running ? "The coach is planning..." : "No plan was recorded."}
      </div>
    );
  }
  const finished = todos.filter((t) => t.status === "completed").length;
  if (job.status === "done") {
    return (
      <details className="group rounded-2xl border border-line bg-panel">
        <summary className="flex cursor-pointer list-none items-center gap-2.5 px-4 py-3 text-sm font-semibold [&::-webkit-details-marker]:hidden">
          <span className="grid size-5 shrink-0 place-items-center rounded-full bg-accent text-black"><CheckIcon className="size-3" /></span>
          <span className="min-w-0 flex-1">{finished === todos.length ? "All steps done" : `${finished} of ${todos.length} steps done`}</span>
          <span className="shrink-0 text-xs font-normal text-muted">{todos.length} steps</span>
          <span aria-hidden className="shrink-0 text-muted transition group-open:rotate-45">+</span>
        </summary>
        <div className="px-2.5 pb-3"><StepList todos={todos} stopped={false} /></div>
      </details>
    );
  }
  const pct = Math.round(job.progress * 100);
  return (
    <section aria-label="The plan" className="rounded-2xl border border-line bg-panel p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="eyebrow">The plan</h2>
        <span className={`shrink-0 text-sm font-bold tabular-nums ${failed ? "text-red-300" : ""}`}>
          {failed ? "Stopped" : `${finished} of ${todos.length} · ${pct}%`}
        </span>
      </div>
      {!failed && (
        <div role="progressbar" aria-label="Coach progress" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}
          className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
          <div className="h-full rounded-full bg-accent transition-[width] duration-500" style={{ width: `${pct}%` }} />
        </div>
      )}
      <div className="-mx-1.5 mt-3"><StepList todos={todos} stopped={failed} /></div>
    </section>
  );
}

/** The main section: what to work on, in Markdown (the biggest fix and a drill), or why there's none. */
export function CoachNotesSection({ job, notes }: { job: Job; notes: CoachNotes | null }) {
  let missing: string | null = null;
  if (!notes && !isRunning(job)) {
    missing = job.status === "failed"
      ? "The job stopped before the coach wrote them."
      : job.warning || "The coach didn't find a stroke of yours to coach. Try a clip where you're closer to the camera.";
  }
  return (
    <section aria-labelledby="coach-notes" className="rounded-3xl border border-accent/40 bg-accent/10 p-5">
      <h2 id="coach-notes" className="eyebrow">Your coaching</h2>
      {notes ? (
        <Markdown text={notes.markdown} className="mt-2" />
      ) : missing ? (
        <div role="status" className="mt-2 space-y-1">
          <p className="text-lg font-semibold">No coaching notes for this video.</p>
          <p className="text-muted [overflow-wrap:anywhere]">{missing}</p>
        </div>
      ) : (
        <p className="mt-2 text-muted">Your coaching notes appear here once the coach has written them.</p>
      )}
    </section>
  );
}

/** Development only: the coach's internal files, wrapped so they can't widen the page. */
function DebugFiles({ files }: { files: NonNullable<Job["agentFiles"]> }) {
  return (
    <details className="group rounded-2xl border border-dashed border-line">
      <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3 text-sm font-semibold text-muted [&::-webkit-details-marker]:hidden">
        <span className="min-w-0 flex-1">Debug: the coach&apos;s working files ({files.length})</span>
        <span className="shrink-0 rounded bg-white/10 px-1.5 py-0.5 text-[0.65rem] uppercase tracking-widest">dev only</span>
        <span aria-hidden className="shrink-0 transition group-open:rotate-45">+</span>
      </summary>
      <div className="space-y-3 px-4 pb-4">
        {files.map((f) => (
          <div key={f.name} className="min-w-0">
            <p className="font-mono text-xs font-bold text-accent">{f.name}</p>
            <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-black/40 p-2 text-xs text-muted light:bg-white/5">
              {f.preview}
            </pre>
          </div>
        ))}
      </div>
    </details>
  );
}

export function CoachView({ job, debug = DEV }: { job: Job; debug?: boolean }) {
  const running = isRunning(job);
  const notes = coachingOf(job);
  const files = job.agentFiles ?? [];
  return (
    <div className="mx-auto max-w-5xl space-y-6 lg:grid lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] lg:items-start lg:gap-10 lg:space-y-0">
      <div className="min-w-0 space-y-4 lg:sticky lg:top-20">
        <div className="space-y-3">
          <p className="eyebrow">TT Coach{job.engine === "deepagents" ? " · deep agent" : ""}</p>
          <h1 className="headline text-3xl [overflow-wrap:anywhere] sm:text-4xl">&ldquo;{str(job.params.request) ?? "Your request"}&rdquo;</h1>
          {job.message && (
            <p className={`[overflow-wrap:anywhere] ${job.status === "failed" ? "text-red-200" : "text-muted"}`}>
              {running && <span className="mr-2 inline-block size-2 animate-pulse rounded-full bg-accent" />}
              {job.message}
            </p>
          )}
        </div>
        <Plan job={job} />
        {job.engine === "fallback" && (
          <p className="text-xs text-muted [overflow-wrap:anywhere]">Ran the same tools on a fixed plan ({job.engineNote}).</p>
        )}
      </div>
      <div className="min-w-0 space-y-8">
        <CoachNotesSection job={job} notes={notes} />
        {notes && job.warning && <Warning>{job.warning}</Warning>}
        {(job.outputs ?? []).map((o) => (
          <section key={o.kind} className="space-y-3">
            <div className="flex items-end justify-between gap-3">
              <div className="min-w-0">
                <h2 className="headline text-3xl [overflow-wrap:anywhere]">{o.title}</h2>
                <p className="text-sm text-muted [overflow-wrap:anywhere]">{o.summary}</p>
              </div>
              <a href={o.url} download className={`${secondaryButtonClass} h-10 shrink-0`}><DownloadIcon /> Save</a>
            </div>
            <video
              src={`${o.url}#t=0.001`} controls playsInline preload="metadata"
              className={`mx-auto block w-full rounded-3xl border border-line bg-black object-contain ${o.kind === "highlights" ? "aspect-video" : "max-h-[78svh]"}`}
            />
          </section>
        ))}
        {running && !(job.outputs ?? []).length && <div className="stripes aspect-video rounded-3xl border border-line bg-panel" />}
        <AnalysedPlayer job={job} />
        {/* The notes already hold the drill, so the breakdown doesn't repeat it. */}
        {job.breakdown && <Steps b={job.breakdown} drill={!notes} />}
        {job.matches && job.matches.length > 0 && <Matches matches={job.matches} stroke={str(job.params.stroke)} />}
        {debug && files.length > 0 && <DebugFiles files={files} />}
        {!running && <Link href="/coach" className={secondaryButtonClass}>Ask again</Link>}
      </div>
    </div>
  );
}
