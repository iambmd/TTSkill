import Link from "next/link";
import type { RallyClip } from "@/lib/submit";
import { fmtDuration } from "@/lib/validate";

export function MatchSource({ job, form, rallyId, clip }: {
  job: string; form: "coach" | "breakdown"; rallyId?: string; clip?: RallyClip;
}) {
  return (
    <div className="surface-card space-y-2 p-4">
      <input type="hidden" name="source_job" value={job} />
      {rallyId && <input type="hidden" name="source_rally" value={rallyId} />}
      <p className="font-semibold">{rallyId ? "Using your selected rally" : "Using your uploaded match"}</p>
      {clip && <p className="text-sm text-muted">Rally {clip.id} · {fmtDuration(clip.start)} – {fmtDuration(clip.end)} in the match</p>}
      <Link href={`/${form}`} className="inline-flex min-h-11 items-center text-sm font-semibold text-accent underline">
        Choose a different video
      </Link>
    </div>
  );
}
