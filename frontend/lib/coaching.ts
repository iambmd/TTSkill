/** Which coaching notes a Coach job page shows. */
import type { CoachNotes, Job } from "./submit";

/** The backend's `coaching` field. Jobs from before it existed (the cached demo jobs) only have
 * `summary`, which was their notes, so that stands in for them. Null means there are none. */
export function coachingOf(job: Job): CoachNotes | null {
  if ("coaching" in job) return job.coaching?.markdown.trim() ? job.coaching : null;
  const md = job.summary?.trim();
  if (job.status !== "done" || !md || md === "Done.") return null;
  return { markdown: md, fix: "", drill: job.breakdown?.drill ?? "" };
}
