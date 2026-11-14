export type Job = {
  id: string;
  kind: "breakdown" | "autocut";
  status: "queued" | "running" | "done" | "failed";
  progress: number;
  message?: string;
  params: Record<string, unknown>;
  resultUrl?: string | null;
};

/** Posts a form to one of our API routes and returns the created job. */
export async function submitJob(path: string, form: FormData): Promise<Job> {
  const res = await fetch(path, { method: "POST", body: form });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error ?? `Request failed (${res.status})`);
  return data as Job;
}
