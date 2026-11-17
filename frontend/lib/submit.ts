export type Job = {
  id: string;
  kind: "breakdown" | "autocut" | "match" | "coach";
  status: "queued" | "running" | "done" | "failed";
  progress: number;
  message?: string;
  params: Record<string, unknown>;
  resultUrl?: string | null;
  breakdown?: Breakdown;
  rallies?: { start: number; end: number; hits: number; shots: number }[];
  /** Auto-Cut: advice when too few rallies were heard (the job still counts as done). */
  warning?: string | null;
  strokeType?: { key: string | null; label: string; detected: boolean } | null;
  matches?: ProMatch[];
  todos?: { content: string; status: "pending" | "in_progress" | "completed" }[];
  agentFiles?: { name: string; preview: string }[];
  outputs?: { kind: string; title: string; url: string; summary: string }[];
  engine?: "deepagents" | "fallback";
  engineNote?: string;
  summary?: string;
  you?: { bat_hand: string; height: { height_cm: number; method: string } | null };
};

export type ProMatch = {
  id: string;
  name: string;
  country?: string;
  height_cm: number;
  bat_hand: string;
  grip?: "shakehand" | "penhold";
  /** Why to copy part of this pro with care: equipment (e.g. anti-spin backhand) or penhold grip. */
  warnings?: string[];
  score: number;
  form_score: number | null;
  differences: string[];
  /** The pro's cached breakdown of this stroke; null when no usable clip exists. */
  breakdown?: string | null;
  source_url?: string | null;
};

/** Mirrors StrokeBreakdown in backend/technique/schema.py. */
export type Breakdown = {
  player: string;
  stroke: string;
  stroke_type?: string | null;
  handedness: string;
  headline: string;
  grip: string;
  stance: string;
  swing_path: string;
  contact_point: string;
  follow_through: string;
  steps: { title: string; lines: string[]; highlight_words: string[]; key_time_s: number; callouts: string[] }[];
  recap?: string | null;
  drill?: string | null;
};

/**
 * The backend's public URL (e.g. a Cloudflare tunnel), inlined at build time. When set, the browser posts
 * jobs and loads result videos straight from it: Vercel Functions cap request and response bodies at 4.5 MB,
 * far below a phone video. Unset, everything goes through this app's /api routes.
 */
export const PUBLIC_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").trim().replace(/\/+$/, "");

/** Where a new job is posted: the public backend when there is one, else our /api/jobs route. */
export function jobEndpoint(kind: Job["kind"]): string {
  return PUBLIC_API_URL ? `${PUBLIC_API_URL}/jobs/${kind}` : `/api/jobs/${kind}`;
}

/**
 * Posts a form for a new job and returns the created job.
 * Uses XHR rather than fetch because only XHR reports upload progress, which matters for big phone videos.
 */
export function submitJob(kind: Job["kind"], form: FormData, onProgress?: (fraction: number) => void): Promise<Job> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", jobEndpoint(kind));
    xhr.responseType = "json";
    if (onProgress) xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
    xhr.onload = () => {
      const data = xhr.response ?? {};
      if (xhr.status >= 200 && xhr.status < 300) return resolve(data as Job);
      if (xhr.status === 413) return reject(new Error("That video is too big to upload here. Try a shorter clip."));
      // Our routes answer {error}; FastAPI, reached directly, answers {detail}.
      const detail = typeof data.detail === "string" ? data.detail : undefined;
      reject(new Error(data.error ?? detail ?? `Request failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new Error(PUBLIC_API_URL
      ? "Can't reach the TTSkill backend. Check your connection, then try again."
      : "Upload failed. Check your connection and try again."));
    xhr.send(form);
  });
}
