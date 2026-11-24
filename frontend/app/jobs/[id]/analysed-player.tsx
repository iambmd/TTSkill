"use client";

/** "Analysed: [thumbnail] · Change player". Change player opens the picker on this job's video
 * and re-runs the job following the newly tapped player. */
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { Job } from "@/lib/submit";
import { PlayerPicker } from "../../player-picker";

const KINDS = ["breakdown", "match", "coach"] as const;
type Kind = (typeof KINDS)[number];

export function AnalysedPlayer({ job }: { job: Job }) {
  const t = useTranslations("analysedPlayer");
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const ended = job.status === "done" || job.status === "failed";
  const picked = !!job.params.player_pick;
  // Cached demo jobs have no stored video to re-run.
  const canChange = ended && (KINDS as readonly string[]).includes(job.kind) && !job.id.startsWith("demo-");
  if (!job.player?.thumb && !(canChange && picked)) return null;

  async function rerun(choice: { time: number; box: [number, number, number, number] }) {
    setStarting(true);
    setError(null);
    const form = new FormData();
    form.set("player_time", String(choice.time));
    form.set("player_box", choice.box.join(","));
    const res = await fetch(`/api/jobs/${job.id}/rerun`, { method: "POST", body: form });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setError(data.error ?? t("rerunFailed"));
      setStarting(false);
      return;
    }
    router.push(`/jobs/${data.id}`);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 rounded-xl border border-line bg-panel p-2 pr-4">
        {job.player?.thumb && <img src={job.player.thumb} alt={t("thumb")} className="h-14 w-auto rounded-lg" />}
        <p className="flex-1 text-sm text-muted">{job.player?.thumb ? (picked ? t("picked") : t("this")) : t("pickToRetry")}</p>
        {canChange && !open && (
          <button type="button" onClick={() => setOpen(true)} className="min-h-11 text-sm font-bold text-accent hover:text-accent-hot">
            {t("change")}
          </button>
        )}
      </div>
      {open && (
        <PlayerPicker
          previewUrl={null} duration={null} link={null} kind={job.kind as Kind} jobId={job.id}
          onProblem={() => {}} onChoice={starting ? undefined : rerun}
        />
      )}
      {starting && <p aria-live="polite" className="text-sm text-muted">{t("starting")}</p>}
      {error && <p role="alert" className="text-sm text-red-200">{error}</p>}
    </div>
  );
}
