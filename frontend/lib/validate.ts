/**
 * Input checks shared by the forms (inline errors, submit disabled) and the API routes (422s).
 * The limits live in shared/limits.json, which backend/app/validate.py reads too, and the
 * messages match the backend's. Only the backend can see a file's tracks, or a link's
 * privacy and length, so those checks happen there.
 */
import LIMITS from "../../shared/limits.json";
import { linkProblem } from "./youtube";

export { LIMITS };
export type Kind = keyof typeof LIMITS.link_max_seconds;
type ChoiceKey = keyof typeof LIMITS.choices;
type RangeKey = Exclude<keyof typeof LIMITS.autocut, "min_rallies">;
type TextKey = keyof typeof LIMITS.text_chars;

const UP = LIMITS.upload;
const H = LIMITS.height_cm;
const NUMBER = /^[0-9]+(\.[0-9]+)?$/;
const INCH_CM = 2.54;

const or = (xs: readonly string[]) => (xs.length > 1 ? `${xs.slice(0, -1).join(", ")} or ${xs.at(-1)}` : xs[0]);
export const fmtDuration = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
export const minutes = (s: number) => `${Math.round(s / 60)} minutes`;

const EXT_NAMES = or(UP.extensions.map((e) => (e === "webm" ? "WebM" : e.toUpperCase())));

/** A 422 with the error the form shows. */
export const invalid = (error: string) => Response.json({ error }, { status: 422 });

/** Extension and size, checked as soon as a file is picked. */
export function fileProblem(file: { name: string; size: number }): string | null {
  const ext = file.name.includes(".") ? file.name.split(".").pop()!.toLowerCase() : "";
  if (!UP.extensions.includes(ext)) return `Upload a video file: ${EXT_NAMES}.`;
  if (file.size > UP.max_mb * 1e6) {
    return `That file is ${(file.size / 1e6).toFixed(0)} MB. Upload one under ${UP.max_mb} MB, or trim it first.`;
  }
  return null;
}

/** Length and resolution from the browser's preview, when it can read them (width 0 = unknown). */
export function mediaProblem({ duration, width, height }: { duration: number; width: number; height: number }): string | null {
  if (Number.isFinite(duration) && duration > 0) {
    if (duration < UP.min_seconds) {
      return `That clip is only ${duration.toFixed(1)} s long. Upload at least ${UP.min_seconds} seconds of play.`;
    }
    if (duration > UP.max_seconds) {
      return `That video is ${fmtDuration(duration)} long. Uploads can be up to ${minutes(UP.max_seconds)}: trim it and try again.`;
    }
  }
  if (width > 0 && height > 0 && Math.min(width, height) < UP.min_short_side) {
    return `That video is only ${width}x${height}, too small to see the stroke. Re-record it at 480p or higher (your phone's normal video setting is fine).`;
  }
  return null;
}

/** Optional height in cm, as typed. */
export function heightProblem(raw: string): string | null {
  const v = raw.trim();
  if (!v) return null;
  if (!NUMBER.test(v)) return `Enter your height as a number in cm, between ${H.min} and ${H.max}.`;
  const cm = Number(v);
  if (cm < H.min || cm > H.max) return `Height must be between ${H.min} and ${H.max} cm. Leave it empty and we estimate it from the table.`;
  return null;
}

/** The cm limits as whole feet and inches, rounded inwards so both ends are valid. */
const inches = (cm: number, round: (x: number) => number) => round(cm / INCH_CM);
const ftIn = (total: number) => `${Math.floor(total / 12)} ft ${total % 12} in`;
export const HEIGHT_FT_RANGE = `${ftIn(inches(H.min, Math.ceil))} and ${ftIn(inches(H.max, Math.floor))}`;

/** Feet + inches as typed -> { cm } or { error }. Both empty is fine (height is optional). */
export function feetInches(ft: string, inch: string): { cm: number | null; error: string | null } {
  const f = ft.trim();
  const i = inch.trim() || "0";
  if (!f && !inch.trim()) return { cm: null, error: null };
  if (!/^[0-9]+$/.test(f) || !NUMBER.test(i)) return { cm: null, error: "Enter whole feet and inches as numbers, e.g. 5 ft 10 in." };
  if (Number(i) >= 12) return { cm: null, error: "Inches go from 0 to 11." };
  const cm = Math.round((Number(f) * 12 + Number(i)) * INCH_CM * 10) / 10;
  if (cm < H.min || cm > H.max) return { cm: null, error: `Height must be between ${HEIGHT_FT_RANGE}. Leave it empty and we estimate it from the table.` };
  return { cm, error: null };
}

/** Trimmed text within LIMITS.text_chars. Empty is the caller's call. */
export function textProblem(raw: string, key: TextKey, label: string): string | null {
  const n = raw.trim().length;
  const most = LIMITS.text_chars[key];
  return n > most ? `${label} can be up to ${most} characters (it has ${n}). Shorten it and try again.` : null;
}

export function choiceProblem(value: string, key: ChoiceKey, label: string): string | null {
  const allowed: readonly string[] = LIMITS.choices[key];
  return allowed.includes(value) ? null : `${label} must be ${or(allowed)}.`;
}

/** An Auto-Cut setting as typed. Blank means "use the default". */
export function rangeProblem(raw: string, key: RangeKey, label: string, whole = false): string | null {
  const v = raw.trim();
  if (!v) return null;
  if (!(whole ? /^-?[0-9]+$/ : /^-?[0-9]+(\.[0-9]+)?$/).test(v)) return `${label} must be a ${whole ? "whole number" : "number"}.`;
  const { min, max } = LIMITS.autocut[key];
  const n = Number(v);
  return n < min || n > max ? `${label} must be between ${min} and ${max}.` : null;
}

/** An upload already on the server (the picker sent it because the browser couldn't read it). */
export const STAGED = /^[0-9a-f]{32}\.(mp4|mov|webm|mkv)$/;

/** The video part of a submitted form: an upload already on the server, then a non-empty
 * file, then a link. */
export function videoInputProblem(form: FormData, missing: string, reuseMatch = false): string | null {
  const source = reuseMatch ? String(form.get("source_job") ?? "") : "";
  if (source) {
    if (!/^[0-9a-f]{32}$/.test(source)) return "Open your match result or upload the video again.";
    const rally = String(form.get("source_rally") ?? "");
    return !rally || /^[1-9][0-9]*$/.test(rally) ? null : "Open your match result and choose a rally again.";
  }
  const staged = String(form.get("staged") ?? "").trim();
  if (staged) return STAGED.test(staged) ? null : "Choose the video again.";
  const video = form.get("video");
  if (video instanceof File && video.size > 0) return fileProblem(video);
  const url = String(form.get("url") ?? "").trim();
  return url ? linkProblem(url) : missing;
}

/** Frames for "Which one is you?" (POST /api/players/detect): JPEG or PNG stills the browser drew
 * from the chosen video, each with its time, or a YouTube link instead. Same rules as the API. */
export function playerFramesProblem(form: FormData): string | null {
  const P = LIMITS.players;
  const job = String(form.get("job") ?? "");
  if (job) return /^[0-9a-f]{32}$/.test(job) ? null : "Unknown job.";   // "Change player" on a result
  const video = form.get("video");
  if (video instanceof File && video.size > 0) return fileProblem(video);   // the browser couldn't read its frames
  const frames = form.getAll("frames").filter((f): f is File => f instanceof File && f.size > 0);
  if (!frames.length) {
    const url = String(form.get("url") ?? "").trim();
    return url ? linkProblem(url) : "Send at least one frame of the video, or a YouTube link.";
  }
  if (frames.length > P.max_frames) return `Send at most ${P.max_frames} frames.`;
  const times = String(form.get("times") ?? "").split(",").filter((t) => t.trim());
  if (times.length !== frames.length || !times.every((t) => NUMBER.test(t.trim()))) {
    return "Each frame needs its time in the video, in seconds.";
  }
  if (frames.some((f) => f.size > P.max_frame_kb * 1024)) return `Each frame must be under ${P.max_frame_kb} KB.`;
  if (frames.some((f) => !["image/jpeg", "image/png"].includes(f.type))) return "Frames must be JPEG or PNG images.";
  return null;
}

/** The "Only me in the video" box: "1" when ticked, missing or "" when not. Same rule as the API. */
export function onlyMeProblem(form: FormData): string | null {
  const allowed: readonly string[] = LIMITS.choices.only_me;
  return allowed.includes(String(form.get("only_me") ?? "")) ? null : "“Only me in the video” must be ticked or not.";
}

/** The player tapped in "Which one is you?" (player_time + player_box "x0,y0,x1,y1", 0-1).
 * Both missing is fine: the analysis then picks the player itself. Same rule as the API. */
export function playerSelectionProblem(form: FormData): string | null {
  const time = String(form.get("player_time") ?? "").trim();
  const box = String(form.get("player_box") ?? "").trim();
  if (!time && !box) return null;
  const again = "The player you picked didn't come through. Pick the player again.";
  const parts = box.split(",").map((v) => v.trim());
  if (!NUMBER.test(time) || parts.length !== 4 || !parts.every((v) => NUMBER.test(v))) return again;
  const [x0, y0, x1, y1] = parts.map(Number);
  return 0 <= x0 && x0 < x1 && x1 <= 1 && 0 <= y0 && y0 < y1 && y1 <= 1 ? null : again;
}
