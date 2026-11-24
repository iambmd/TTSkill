import "server-only";
import { randomUUID } from "crypto";
import { unavailableStatus } from "./analysis-status";
import { english } from "./english";
import type { Tr } from "./messages";
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

// Messages below come in the request's language: routes pass translator(requestLocale(req), "errors").
const EN: Tr = english("errors");
const OFFLINE = english("offline")("analysis");
export const UNREACHABLE = EN("unreachable");

/** fetch() to the backend that answers 502 with a readable error when it is down, instead of throwing. */
async function backend(path: string, init?: RequestInit, t: Tr = EN): Promise<Response> {
  try {
    return await fetch(`${BACKEND_URL}${path}`, init);
  } catch {
    return Response.json({ error: t("unreachable") }, { status: 502 });
  }
}

/** Reachability check for Home. An offline backend is a successful probe with ok: false. */
export async function backendHealth(): Promise<Response> {
  let ok = DEMO_MODE && !PUBLIC_API_URL;
  if (!ok && BACKEND_URL) {
    const res = await backend("/health", { cache: "no-store", signal: AbortSignal.timeout(4000) });
    const body = await res.json().catch(() => null);
    ok = res.ok && body?.ok === true;
  }
  return Response.json({ ok }, { headers: { "cache-control": "no-store" } });
}

/** Summarizes a form for the job record, replacing files with their name and size. */
function describeForm(form: FormData): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of form.entries()) {
    out[k] = typeof v === "string" ? v : { file: v.name, bytes: v.size, type: v.type };
  }
  return out;
}

/** `offline`: the "analysis server is offline" sentence in the request's language. */
export async function createJob(kind: Job["kind"], form: FormData, t: Tr = EN, offline = OFFLINE): Promise<Response> {
  if (DEMO_MODE && DEMO_JOBS[`demo-${kind}`]) return Response.json(DEMO_JOBS[`demo-${kind}`], { status: 201 });
  if (BACKEND_URL) {
    const res = await backend(`/jobs/${kind}`, { method: "POST", body: form }, t);
    const data = await res.json().catch(() => ({}));
    // FastAPI reports errors as {detail}; the client reads {error}.
    if (!res.ok) {
      if (unavailableStatus(res.status)) return Response.json({ error: offline }, { status: res.status });
      const detail = typeof data.detail === "string" ? data.detail : data.error ?? t("rejected");
      return Response.json({ error: detail }, { status: res.status });
    }
    return Response.json(data, { status: res.status });
  }
  const job: Job = {
    id: randomUUID(),
    kind,
    status: "queued",
    progress: 0,
    message: t("stubJob"),
    params: describeForm(form),
    resultUrl: null,
  };
  stubJobs.set(job.id, job);
  return Response.json(job, { status: 201 });
}

/** "Which one is you?": the players in frames of the chosen video. Without a backend (stub or
 * demo mode) nothing can look, so the answer says so and the picker stays hidden. */
export async function detectPlayers(form: FormData, signal?: AbortSignal, t: Tr = EN): Promise<Response> {
  if (DEMO_MODE || !BACKEND_URL) return Response.json({ candidates: [], frame: null, available: false });
  const start = Date.now();
  // Pass the browser's abort on, so the backend stops working for a page that left.
  const res = await backend("/players/detect", { method: "POST", body: form, signal }, t);
  const data = await res.json().catch(() => ({}));
  const ms = Date.now() - start;
  console.info(detectLog(form, res.status, ms, data));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : data.error ?? t("rejected");
    return Response.json({ error: detail }, { status: res.status });
  }
  if (data.timing) data.timing.next_s = Number((ms / 1000).toFixed(2));
  return Response.json(data);
}

/** One line per "Which one is you?" lookup in the Next.js log: what the browser sent and how
 * long it spent drawing frames, against the backend's own split of the time. */
export function detectLog(form: FormData, status: number, ms: number, data: { timing?: Record<string, number>; candidates?: unknown[] }): string {
  const frames = form.getAll("frames").filter((f): f is File => f instanceof File);
  const kb = Math.round(frames.reduce((n, f) => n + f.size, 0) / 1024);
  const video = form.get("video");
  const sent = frames.length ? `${frames.length} frames, ${kb} KB, drawn in ${form.get("grab_ms") ?? "?"} ms`
    : video instanceof File && video.size ? `the whole video (${Math.round(video.size / 1e6)} MB; the browser couldn't read it)`
    : form.get("job") ? "a past job's video" : "a link";
  const t = data.timing;
  const backendPart = t ? `backend ${t.total_s ?? t.seconds} s (detect ${t.seconds} s)` : "no timing";
  return `[players/detect] ${sent} -> ${status} in ${ms} ms; ${backendPart}; ${data.candidates?.length ?? 0} players`;
}

/** "Change player": the same job on the same video, following the newly tapped player. */
export async function rerunJob(id: string, form: FormData, t: Tr = EN): Promise<Response> {
  if (DEMO_MODE || !BACKEND_URL || DEMO_JOBS[id]) {
    return Response.json({ error: t("rerunNeedsBackend") }, { status: 422 });
  }
  const res = await backend(`/jobs/${id}/rerun`, { method: "POST", body: form }, t);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : data.error ?? t("rejected");
    return Response.json({ error: detail }, { status: res.status });
  }
  return Response.json(data, { status: res.status });
}

export async function getJob(id: string, t: Tr = EN): Promise<Response> {
  if (DEMO_JOBS[id]) return Response.json(DEMO_JOBS[id]);
  if (BACKEND_URL) {
    const res = await backend(`/jobs/${id}`, { cache: "no-store" }, t);
    if (!res.ok) return new Response(res.body, { status: res.status, headers: res.headers });
    const job = (await res.json()) as Job;
    // Videos load straight from a public backend, since a Vercel Function can't pass a long video through;
    // otherwise our /api routes proxy them. Coach outputs are served at /jobs/{id}/files/{name}.
    const videos = PUBLIC_API_URL || "/api";
    job.rallyClips = job.rallyClips?.map((clip) => ({
      ...clip, clipUrl: `${videos}${clip.clipUrl}`, thumbnailUrl: `${videos}${clip.thumbnailUrl}`,
    }));
    if (job.previewUrl) job.previewUrl = `${videos}${job.previewUrl}`;
    if (job.resultUrl) job.resultUrl = `${videos}/jobs/${id}/result`;
    job.outputs = job.outputs?.map((o) => ({ ...o, url: `${videos}${o.url}` }));
    return Response.json(job);
  }
  const job = stubJobs.get(id);
  if (!job) return Response.json({ error: t("jobNotFound") }, { status: 404 });
  // Simulate progress so the job page can be exercised without a backend.
  if (job.status !== "done") {
    job.progress = Math.min(1, job.progress + 0.25);
    job.status = job.progress >= 1 ? "done" : "running";
  }
  return Response.json(job);
}

// Headers passed through from the backend so <video> can seek (Safari/iOS needs range requests).
const RESULT_HEADERS = ["content-type", "content-length", "content-range", "accept-ranges", "content-disposition", "etag", "last-modified"];

export async function getResult(id: string, range?: string | null, file?: string, t: Tr = EN): Promise<Response> {
  if (!BACKEND_URL) return Response.json({ error: t("noStubResult") }, { status: 404 });
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


export async function exportHighlights(id: string, rallies: number[], t: Tr = EN): Promise<Response> {
  if (!BACKEND_URL || DEMO_JOBS[id]) return Response.json({ error: t("noRallyClips") }, { status: 404 });
  const res = await backend(`/jobs/${id}/exports`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ rallies }),
  }, t);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return Response.json({ error: data.detail ?? data.error ?? t("exportFailed") }, { status: res.status });
  }
  return Response.json(data);
}
