import "server-only";
import { randomUUID } from "crypto";
import { PUBLIC_API_URL, type Job } from "./submit";
import demoJobs from "./demo-jobs.json";

// How this server reaches FastAPI. On Vercel the public tunnel URL serves for both, so one variable is enough.
export const BACKEND_URL = process.env.BACKEND_URL || PUBLIC_API_URL || undefined;
// DEMO_MODE=1 answers every submission with the cached sample-clip result, so a live demo never waits on the pipeline.
const DEMO_MODE = process.env.DEMO_MODE === "1";
const DEMO_JOBS = demoJobs as Record<string, Job>;

// In-memory store used only when BACKEND_URL is unset (local stub mode).
const g = globalThis as unknown as { __ttskillJobs?: Map<string, Job> };
const stubJobs = (g.__ttskillJobs ??= new Map());

export const UNREACHABLE = "Can't reach the TTSkill backend. Check that it is running (make dev), then try again.";

/** fetch() to the backend that answers 502 with a readable error when it is down, instead of throwing. */
async function backend(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${BACKEND_URL}${path}`, init);
  } catch {
    return Response.json({ error: UNREACHABLE }, { status: 502 });
  }
}

/** Summarizes a form for the job record, replacing files with their name and size. */
function describeForm(form: FormData): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of form.entries()) {
    out[k] = typeof v === "string" ? v : { file: v.name, bytes: v.size, type: v.type };
  }
  return out;
}

export async function createJob(kind: Job["kind"], form: FormData): Promise<Response> {
  if (DEMO_MODE && DEMO_JOBS[`demo-${kind}`]) return Response.json(DEMO_JOBS[`demo-${kind}`], { status: 201 });
  if (BACKEND_URL) {
    const res = await backend(`/jobs/${kind}`, { method: "POST", body: form });
    const data = await res.json().catch(() => ({}));
    // FastAPI reports errors as {detail}; the client reads {error}.
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : data.error ?? "Backend rejected the request";
      return Response.json({ error: detail }, { status: res.status });
    }
    return Response.json(data, { status: res.status });
  }
  const job: Job = {
    id: randomUUID(),
    kind,
    status: "queued",
    progress: 0,
    message: "Stub mode: no backend configured, so nothing is processed.",
    params: describeForm(form),
    resultUrl: null,
  };
  stubJobs.set(job.id, job);
  return Response.json(job, { status: 201 });
}

/** "Which one is you?": the players in a few frames of the chosen video. Without a backend (stub
 * or demo mode) there is nobody to find, so the answer is decisive and the picker stays hidden. */
export async function detectPlayers(form: FormData): Promise<Response> {
  if (DEMO_MODE || !BACKEND_URL) return Response.json({ candidates: [], frame: null, suggested: null, decisive: true });
  const res = await backend("/players/detect", { method: "POST", body: form });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : data.error ?? "Backend rejected the request";
    return Response.json({ error: detail }, { status: res.status });
  }
  return Response.json(data);
}

export async function getJob(id: string): Promise<Response> {
  if (DEMO_JOBS[id]) return Response.json(DEMO_JOBS[id]);
  if (BACKEND_URL) {
    const res = await backend(`/jobs/${id}`, { cache: "no-store" });
    if (!res.ok) return new Response(res.body, { status: res.status });
    const job = (await res.json()) as Job;
    // Videos load straight from a public backend, since a Vercel Function can't pass a long video through;
    // otherwise our /api routes proxy them. Coach outputs are served at /jobs/{id}/files/{name}.
    const videos = PUBLIC_API_URL || "/api";
    if (job.resultUrl) job.resultUrl = `${videos}/jobs/${id}/result`;
    job.outputs = job.outputs?.map((o) => ({ ...o, url: `${videos}${o.url}` }));
    return Response.json(job);
  }
  const job = stubJobs.get(id);
  if (!job) return Response.json({ error: "Job not found" }, { status: 404 });
  // Simulate progress so the job page can be exercised without a backend.
  if (job.status !== "done") {
    job.progress = Math.min(1, job.progress + 0.25);
    job.status = job.progress >= 1 ? "done" : "running";
  }
  return Response.json(job);
}

// Headers passed through from the backend so <video> can seek (Safari/iOS needs range requests).
const RESULT_HEADERS = ["content-type", "content-length", "content-range", "accept-ranges", "content-disposition", "etag", "last-modified"];

export async function getResult(id: string, range?: string | null, file?: string): Promise<Response> {
  if (!BACKEND_URL) return Response.json({ error: "No result in stub mode" }, { status: 404 });
  const path = file ? `files/${encodeURIComponent(file)}` : "result";
  const res = await backend(`/jobs/${id}/${path}`, {
    cache: "no-store",
    headers: range ? { range } : undefined,
  });
  const headers = new Headers();
  for (const h of RESULT_HEADERS) {
    const v = res.headers.get(h);
    if (v) headers.set(h, v);
  }
  return new Response(res.body, { status: res.status, headers });
}
