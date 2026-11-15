import "server-only";
import { randomUUID } from "crypto";
import type { Job } from "./submit";
import demoJobs from "./demo-jobs.json";

const BACKEND_URL = process.env.BACKEND_URL;
// DEMO_MODE=1 answers every submission with the cached sample-clip result, so a live demo never waits on the pipeline.
const DEMO_MODE = process.env.DEMO_MODE === "1";
const DEMO_JOBS = demoJobs as Record<string, Job>;

// In-memory store used only when BACKEND_URL is unset (local stub mode).
const g = globalThis as unknown as { __ttskillJobs?: Map<string, Job> };
const stubJobs = (g.__ttskillJobs ??= new Map());

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
    const res = await fetch(`${BACKEND_URL}/jobs/${kind}`, { method: "POST", body: form });
    const data = await res.json().catch(() => ({}));
    // FastAPI reports errors as {detail}; the client reads {error}.
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : "Backend rejected the request";
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

export async function getJob(id: string): Promise<Response> {
  if (DEMO_JOBS[id]) return Response.json(DEMO_JOBS[id]);
  if (BACKEND_URL) {
    const res = await fetch(`${BACKEND_URL}/jobs/${id}`, { cache: "no-store" });
    if (!res.ok) return new Response(res.body, { status: res.status });
    const job = (await res.json()) as Job;
    if (job.resultUrl) job.resultUrl = `/api/jobs/${id}/result`;
    // Coach outputs are served by the backend at /jobs/{id}/files/{name}; route them through us.
    job.outputs = job.outputs?.map((o) => ({ ...o, url: `/api${o.url}` }));
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
  const res = await fetch(`${BACKEND_URL}/jobs/${id}/${path}`, {
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
