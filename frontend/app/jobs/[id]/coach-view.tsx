/** The TT Coach result page: the request and the plan on the left (stacked on phones), the
 * coaching notes first on the right, then the videos, the breakdown and the pro matches.
 *
 * Every grid and flex child that holds text has min-width 0 (`minmax(0, ...)` tracks): a grid
 * track sized `1fr` can't shrink below its widest content, so one unbroken line (the raw JSON
 * files this page used to show) pushed the right column wider than the page and squeezed the
 * plan to a word per line. */
import Link from "next/link";
import { useTranslations } from "next-intl";
import { coachingOf } from "@/lib/coaching";
import type { CoachNotes, Job } from "@/lib/submit";
import { EnglishOnly, useEnglishBlock } from "../../english-only";
import { jobText } from "@/lib/server-text";
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
const DEMO_OUTPUTS: Record<string, string> = { highlights: "coachHighlights", breakdown: "coachBreakdown" };
const isDemo = (job: Job) => job.id.startsWith("demo-");

function StepIcon({ status, stopped }: { status: Todo["status"]; stopped: boolean }) {
  if (status === "completed") {
    return <span className="grid size-5 shrink-0 place-items-center rounded-full action-fill"><CheckIcon className="size-3" /></span>;
  }
  if (status === "in_progress") {
    return stopped ? (
      <span className="grid size-5 shrink-0 place-items-center rounded-full border-2 border-red-400 text-[0.6rem] font-bold text-red-400">!</span>
    ) : (
      <span className="grid size-5 shrink-0 place-items-center rounded-full border-2 border-accent"><span className="size-1.5 animate-pulse rounded-full bg-accent" /></span>
    );
  }
  return <span className="size-5 shrink-0 rounded-full border-2 border-line" />;
}

function StepList({ todos, stopped, cached }: { todos: Todo[]; stopped: boolean; cached: boolean }) {
  const t = useTranslations("coachView");
  const english = useEnglishBlock(cached);
  return (
    <ol className="space-y-0.5" aria-live="polite" {...english}>
      {todos.map((todo, i) => (
        <li key={i} className={`flex items-start gap-2.5 rounded-lg px-1.5 py-1 text-sm ${todo.status === "in_progress" ? "bg-accent/10 font-semibold" : ""}`}>
          <StepIcon status={todo.status} stopped={stopped} />
          <span className={`min-w-0 flex-1 [overflow-wrap:anywhere] ${todo.status === "completed" ? "text-muted" : ""}`}>
            {todo.content}
            {todo.status === "completed" && <span className="sr-only">{t("done")}</span>}
            {todo.status === "in_progress" && !stopped && <span className="sr-only">{t("inProgress")}</span>}
            {stopped && todo.status === "in_progress" && <span className="font-normal text-red-300">{t("stoppedHere")}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}

/** While the job runs: a compact checklist with a progress bar. Done: one "All steps done" line
 * that opens to the list. Failed: the list, showing where it stopped. */
export function Plan({ job }: { job: Job }) {
  const t = useTranslations("coachView");
  const cached = isDemo(job);
  const todos = job.todos ?? [];
  const running = isRunning(job);
  const failed = job.status === "failed";
  if (!todos.length) {
    return (
      <div className={`${running ? "stripes" : ""} coach-plan surface-card p-4 text-sm text-muted`}>
        {running ? t("planning") : t("noPlan")}
      </div>
    );
  }
  const finished = todos.filter((t) => t.status === "completed").length;
  if (job.status === "done") {
    return (
      <details className="group coach-plan surface-card">
        <summary className="flex list-none items-center gap-2.5 px-4 py-3 text-sm font-semibold [&::-webkit-details-marker]:hidden">
          <span className="grid size-5 shrink-0 place-items-center rounded-full action-fill"><CheckIcon className="size-3" /></span>
          <span className="min-w-0 flex-1">{finished === todos.length ? t("allDone") : t("someDone", { done: finished, total: todos.length })}</span>
          <span className="shrink-0 text-xs font-normal text-muted">{t("steps", { n: todos.length })}</span>
          <span aria-hidden className="shrink-0 text-muted transition group-open:rotate-45">+</span>
        </summary>
        <div className="px-2.5 pb-3"><StepList todos={todos} stopped={false} cached={cached} /></div>
      </details>
    );
  }
  const pct = Math.round(job.progress * 100);
  return (
    <section aria-label={t("plan")} className="coach-plan surface-card p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="eyebrow">{t("plan")}</h2>
        <span className={`shrink-0 text-sm font-bold tabular-nums ${failed ? "text-red-300" : ""}`}>
          {failed ? t("stopped") : t("progressText", { done: finished, total: todos.length, pct })}
        </span>
      </div>
      {!failed && (
        <div role="progressbar" aria-label={t("progress")} aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}
          className="coach-progress mt-3 h-1.5 overflow-hidden rounded-full">
          <div className="h-full rounded-full bg-accent transition-[width] duration-300" style={{ width: `${pct}%` }} />
        </div>
      )}
      <div className="-mx-1.5 mt-3"><StepList todos={todos} stopped={failed} cached={cached} /></div>
    </section>
  );
}

/** The main section: what to work on, in Markdown (the biggest fix and a drill), or why there's none. */
export function CoachNotesSection({ job, notes }: { job: Job; notes: CoachNotes | null }) {
  const t = useTranslations("coachView");
  const tAll = useTranslations();
  const cached = isDemo(job);
  const english = useEnglishBlock(cached);
  let missing: string | null = null;
  if (!notes && !isRunning(job)) {
    missing = job.status === "failed" ? t("stoppedEarly") : jobText(job.warning, job.warningRef, tAll) || t("noStroke");
  }
  return (
    <section aria-labelledby="coach-notes" className="coach-notes min-w-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 id="coach-notes" className="headline">{t("yourCoaching")}</h2>
        {notes && cached && <EnglishOnly />}
      </div>
      {notes ? (
        <div {...english}><Markdown text={notes.markdown} className="mt-2" /></div>
      ) : missing ? (
        <div role="status" className="mt-2 space-y-1">
          <p className="text-lg font-semibold">{t("noNotes")}</p>
          <p className="text-muted [overflow-wrap:anywhere]">{missing}</p>
        </div>
      ) : (
        <p className="mt-2 text-muted">{t("notesSoon")}</p>
      )}
    </section>
  );
}

/** Development only: the coach's internal files, wrapped so they can't widen the page. */
function DebugFiles({ files }: { files: NonNullable<Job["agentFiles"]> }) {
  const t = useTranslations("coachView");
  return (
    <details className="group rounded-2xl border border-dashed border-line">
      <summary className="flex list-none items-center gap-3 px-4 py-3 text-sm font-semibold text-muted [&::-webkit-details-marker]:hidden">
        <span className="min-w-0 flex-1">{t("debug", { n: files.length })}</span>
        <span className="shrink-0 rounded bg-white/10 px-1.5 py-0.5 text-[0.65rem] uppercase tracking-widest">{t("devOnly")}</span>
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
  const t = useTranslations();
  const cached = isDemo(job);
  const english = useEnglishBlock(cached);
  const running = isRunning(job);
  const notes = coachingOf(job);
  const files = job.agentFiles ?? [];
  return (
    <div className="coach-surface coach-result mx-auto max-w-5xl space-y-8 lg:grid lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)] lg:items-start lg:gap-10 lg:space-y-0">
      <div className="min-w-0 space-y-4 lg:sticky lg:top-20">
        <div className="space-y-3">
          <p className="eyebrow">TT Coach{job.engine === "deepagents" ? t("coachView.deepAgent") : ""}</p>
          <h1 className="headline text-3xl [overflow-wrap:anywhere] sm:text-4xl" {...english}>&ldquo;{str(job.params.request) ?? t("coachView.yourRequest")}&rdquo;</h1>
          {job.status !== "failed" && (
            <p role="status" className="text-muted [overflow-wrap:anywhere]">
              {running && job.message && <span aria-hidden className="mr-2 inline-block size-2 animate-pulse rounded-full bg-accent" />}
              {/* Progress text comes from the backend; its final "Done." is the one we can name here. */}
              {job.message === "Done." && !job.messageRef ? t("job.status.done") : jobText(job.message, job.messageRef, t)}
            </p>
          )}
        </div>
        <Plan job={job} />
        {job.engine === "fallback" && (
          <p className="text-xs text-muted [overflow-wrap:anywhere]">{t("coachView.backupPlan")}</p>
        )}
      </div>
      <div className="coach-result-content grid min-w-0 grid-cols-[minmax(0,1fr)] gap-8">
        <CoachNotesSection job={job} notes={notes} />
        {notes && job.warning && <Warning>{jobText(job.warning, job.warningRef, t)}</Warning>}
        {(job.outputs ?? []).map((o) => (
          <section key={o.kind} className="coach-output min-w-0 space-y-3">
            <div className="flex items-end justify-between gap-3">
              <div className="min-w-0">
                <h2 id={`output-${o.kind}-title`} className="headline text-3xl [overflow-wrap:anywhere]" {...english}>{o.title}</h2>
                <p id={`output-${o.kind}-description`} className="text-sm text-muted [overflow-wrap:anywhere]">
                  {job.id === "demo-coach" && DEMO_OUTPUTS[o.kind] ? t(`demoDescriptions.${DEMO_OUTPUTS[o.kind]}`) : o.summary}
                </p>
              </div>
              <a href={o.url} download aria-label={t("coachView.saveLabel", { title: o.title })} className={`${secondaryButtonClass} h-11 shrink-0`}><DownloadIcon /> {t("common.save")}</a>
            </div>
            <video
              src={`${o.url}#t=0.001`} controls playsInline preload="metadata"
              aria-labelledby={`output-${o.kind}-title`} aria-describedby={`output-${o.kind}-description`}
              className={`coach-video video-frame mx-auto block w-full border object-contain ${o.kind === "highlights" ? "aspect-video" : "max-h-[78svh]"}`}
            />
          </section>
        ))}
        {running && !(job.outputs ?? []).length && <div className="stripes coach-plan surface-card aspect-video" />}
        <AnalysedPlayer job={job} />
        {/* The notes already hold the drill, so the breakdown doesn't repeat it. */}
        {job.breakdown && <Steps b={job.breakdown} drill={!notes} cached={cached} />}
        {job.matches && job.matches.length > 0 && <Matches matches={job.matches} stroke={str(job.params.stroke)} cached={cached} />}
        {debug && files.length > 0 && <DebugFiles files={files} />}
        {!running && <Link href="/coach" className={`${secondaryButtonClass} justify-self-start`}>{t("coachView.askAgain")}</Link>}
      </div>
    </div>
  );
}
