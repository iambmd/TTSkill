import Link from "next/link";
import { useTranslations } from "next-intl";
import type { RallyClip } from "@/lib/submit";
import { fmtDuration } from "@/lib/validate";

export function MatchSource({ job, form, rallyId, clip }: {
  job: string; form: "coach" | "breakdown"; rallyId?: string; clip?: RallyClip;
}) {
  const t = useTranslations("matchSource");
  return (
    <div className="surface-card space-y-2 p-4">
      <input type="hidden" name="source_job" value={job} />
      {rallyId && <input type="hidden" name="source_rally" value={rallyId} />}
      <p className="font-semibold">{rallyId ? t("rally") : t("match")}</p>
      {clip && <p className="text-sm text-muted">{t("clip", { id: clip.id, start: fmtDuration(clip.start), end: fmtDuration(clip.end) })}</p>}
      <Link href={`/${form}`} className="inline-flex min-h-11 items-center text-sm font-semibold text-accent underline">
        {t("change")}
      </Link>
    </div>
  );
}
