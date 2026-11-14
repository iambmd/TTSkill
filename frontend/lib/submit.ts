export type Job = {
  id: string;
  kind: "breakdown" | "autocut";
  status: "queued" | "running" | "done" | "failed";
  progress: number;
  message?: string;
  params: Record<string, unknown>;
  resultUrl?: string | null;
  breakdown?: Breakdown;
  rallies?: { start: number; end: number; hits: number; shots: number }[];
};

/** Mirrors StrokeBreakdown in backend/technique/schema.py. */
export type Breakdown = {
  player: string;
  stroke: string;
  handedness: string;
  headline: string;
  grip: string;
  stance: string;
  swing_path: string;
  contact_point: string;
  follow_through: string;
  steps: { title: string; lines: string[]; highlight_words: string[]; key_time_s: number; callouts: string[] }[];
};

/** Posts a form to one of our API routes and returns the created job. */
export async function submitJob(path: string, form: FormData): Promise<Job> {
  const res = await fetch(path, { method: "POST", body: form });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error ?? `Request failed (${res.status})`);
  return data as Job;
}
