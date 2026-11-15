export type Job = {
  id: string;
  kind: "breakdown" | "autocut" | "match";
  status: "queued" | "running" | "done" | "failed";
  progress: number;
  message?: string;
  params: Record<string, unknown>;
  resultUrl?: string | null;
  breakdown?: Breakdown;
  rallies?: { start: number; end: number; hits: number; shots: number }[];
  strokeType?: { key: string | null; label: string; detected: boolean } | null;
  matches?: ProMatch[];
  you?: { bat_hand: string; height: { height_cm: number; method: string } | null };
};

export type ProMatch = {
  id: string;
  name: string;
  country?: string;
  height_cm: number;
  bat_hand: string;
  score: number;
  form_score: number | null;
  differences: string[];
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
 * Posts a form to one of our API routes and returns the created job.
 * Uses XHR rather than fetch because only XHR reports upload progress, which matters for big phone videos.
 */
export function submitJob(path: string, form: FormData, onProgress?: (fraction: number) => void): Promise<Job> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", path);
    xhr.responseType = "json";
    if (onProgress) xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
    xhr.onload = () => {
      const data = xhr.response ?? {};
      if (xhr.status >= 200 && xhr.status < 300) return resolve(data as Job);
      if (xhr.status === 413) return reject(new Error("That video is too big to upload here. Try a shorter clip."));
      reject(new Error(data.error ?? `Request failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new Error("Upload failed. Check your connection and try again."));
    xhr.send(form);
  });
}
