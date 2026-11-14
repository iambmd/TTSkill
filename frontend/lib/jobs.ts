import "server-only";
import { randomUUID } from "crypto";
import type { Job } from "./submit";

const BACKEND_URL = process.env.BACKEND_URL;

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
  if (BACKEND_URL) {
    const res = await fetch(`${BACKEND_URL}/jobs/${kind}`, { method: "POST", body: form });
    return new Response(res.body, { status: res.status, headers: { "content-type": "application/json" } });
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
  if (BACKEND_URL) {
    const res = await fetch(`${BACKEND_URL}/jobs/${id}`, { cache: "no-store" });
    if (!res.ok) return new Response(res.body, { status: res.status });
    const job = (await res.json()) as Job;
    if (job.resultUrl) job.resultUrl = `/api/jobs/${id}/result`;
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

export async function getResult(id: string): Promise<Response> {
  if (!BACKEND_URL) return Response.json({ error: "No result in stub mode" }, { status: 404 });
  const res = await fetch(`${BACKEND_URL}/jobs/${id}/result`);
  return new Response(res.body, { status: res.status, headers: res.headers });
}
