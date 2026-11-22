import type { Job } from "@/lib/submit";

const STAGES = [
  ["preparing", "Getting your video ready"],
  ["extracting_audio", "Preparing the recording"],
  ["finding_rallies", "Finding rallies"],
  ["ranking", "Choosing the highlights"],
  ["rendering", "Making your reel"],
] as const;

export function AutoCutWaiting({ job }: { job: Job }) {
  const stage = job.autocutStage;
  const current = Math.max(0, STAGES.findIndex(([key]) => key === stage?.key));
  const percent = Math.round(job.progress * 100);
  const eta = stage?.etaUntil === undefined ? null : Math.ceil(stage.etaUntil - Date.now() / 1000);
  const label = job.status === "queued" ? "Waiting to start" : STAGES[current][1];
  const count = stage?.total === undefined ? "" : ` (${stage.done ?? 0} of ${stage.total})`;

  return (
    <section aria-labelledby="reel-progress" className="surface-card space-y-4 p-5">
      <h2 id="reel-progress" className="section-title text-xl">Reel progress</h2>
      <p role="status" className="font-semibold">{label}{count}</p>
      <div className="flex items-center gap-3">
        <progress aria-label="Reel progress" value={percent} max={100} className="h-2 min-w-0 flex-1 accent-accent" />
        <span className="text-sm tabular-nums">{percent}%</span>
      </div>
      {eta !== null && <p className="text-sm text-muted">
        {eta <= 0 ? "Taking a little longer than expected…" : `About ${eta < 60 ? `${eta} seconds` : `${Math.ceil(eta / 60)} min`} left`}
      </p>}
      <ol className="space-y-1 text-sm">
        {STAGES.map(([key, text], index) => (
          <li key={key} aria-current={index === current ? "step" : undefined}
            className={`rounded-md px-3 py-2 ${index === current ? "bg-accent/10 font-bold text-fg" : "text-muted"}`}>
            <span className="mr-2" aria-hidden>{index < current ? "✓" : index + 1}</span>{text}
          </li>
        ))}
      </ol>
      {job.previewUrl && (
        <figure className="space-y-2">
          <figcaption className="font-semibold">First clip preview</figcaption>
          <video src={`${job.previewUrl}#t=0.001`} controls playsInline preload="metadata"
            aria-label="First clip preview" className="video-frame w-full max-h-[70svh] border object-contain" />
        </figure>
      )}
    </section>
  );
}
