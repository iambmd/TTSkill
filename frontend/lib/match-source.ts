import "server-only";
import { getJob } from "./jobs";
import type { Job } from "./submit";

export async function getSourceRally(source?: string, rally?: string) {
  if (!source || !/^[0-9a-f]{32}$/.test(source) || !rally || !/^[1-9][0-9]*$/.test(rally)) return undefined;
  const response = await getJob(source).catch(() => null);
  if (!response?.ok) return undefined;
  const job = await response.json() as Job;
  return job.rallyClips?.find((clip) => String(clip.id) === rally);
}
