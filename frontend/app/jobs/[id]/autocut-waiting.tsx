import { useTranslations } from "next-intl";
import type { Job } from "@/lib/submit";

const STAGES = ["preparing", "extracting_audio", "finding_rallies", "ranking", "rendering"] as const;

export function AutoCutWaiting({ job }: { job: Job }) {
  const t = useTranslations("autocutWaiting");
  const tc = useTranslations("common");
  const stage = job.autocutStage;
  const current = Math.max(0, STAGES.findIndex((key) => key === stage?.key));
  const percent = Math.round(job.progress * 100);
  const eta = stage?.etaUntil === undefined ? null : Math.ceil(stage.etaUntil - Date.now() / 1000);
  const label = job.status === "queued" ? t("waiting") : t(`stages.${STAGES[current]}`);
  const count = stage?.total === undefined ? "" : t("count", { done: stage.done ?? 0, total: stage.total });

  return (
    <section aria-labelledby="reel-progress" className="surface-card space-y-4 p-5">
      <h2 id="reel-progress" className="section-title text-xl">{t("title")}</h2>
      <p role="status" className="font-semibold">{label}{count}</p>
      <div className="flex items-center gap-3">
        <progress aria-label={t("title")} value={percent} max={100} className="h-2 min-w-0 flex-1 accent-accent" />
        <span className="text-sm tabular-nums">{percent}%</span>
      </div>
      {eta !== null && <p className="text-sm text-muted">
        {eta <= 0 ? t("slow") : t("left", { time: eta < 60 ? tc("seconds", { n: eta }) : tc("minShort", { n: Math.ceil(eta / 60) }) })}
      </p>}
      <ol className="space-y-1 text-sm">
        {STAGES.map((key, index) => (
          <li key={key} aria-current={index === current ? "step" : undefined}
            className={`rounded-md px-3 py-2 ${index === current ? "bg-accent/10 font-bold text-fg" : "text-muted"}`}>
            <span className="mr-2" aria-hidden>{index < current ? "✓" : index + 1}</span>{t(`stages.${key}`)}
          </li>
        ))}
      </ol>
      {job.previewUrl && (
        <figure className="space-y-2">
          <figcaption className="font-semibold">{t("preview")}</figcaption>
          <video src={`${job.previewUrl}#t=0.001`} controls playsInline preload="metadata"
            aria-label={t("preview")} className="video-frame w-full max-h-[70svh] border object-contain" />
        </figure>
      )}
    </section>
  );
}
