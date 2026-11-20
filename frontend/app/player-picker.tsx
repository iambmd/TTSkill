"use client";

/**
 * "Which one is you?" The analysis needs to know who to follow. We draw frames spread over the
 * file in the browser (no second upload) and ask /api/players/detect who is in them:
 * - nobody: say so, and offer "Analyse anyway" (the job then picks the player itself);
 * - one player: analyse them, with "Change player" in case we got it wrong;
 * - two or more: ask which one.
 * The choice goes with the job as hidden player_time and player_box fields.
 */
import { useEffect, useRef, useState } from "react";
import { playersEndpoint } from "@/lib/submit";

type Box = [number, number, number, number];
type Candidate = { id: number; time: number; box: Box; thumb: string; seen: number; near?: number; background?: string };
type Found = {
  candidates: Candidate[];
  /** People who look like background (still, far from the table, tiny): ignored when counting,
   * shown behind "Show everyone we saw" in case we got it wrong. */
  others?: Candidate[];
  frame: { time: number; image: string; boxes: { id: number; box: Box }[] } | null;
  suggested?: number | null;
  decisive?: boolean;
  /** People found in each frame, and where the time went (for the console log). */
  frames?: { time: number; people: number }[];
  timing?: Record<string, number>;
  /** false when nothing could look (no backend: stub or demo mode), so the picker stays out of the way. */
  available?: boolean;
  /** The video, kept on the server after the browser couldn't read it: the job takes it by this token. */
  staged?: string;
};
type Choice = { id: number; time: number; box: Box };

/** Frames drawn per video, spread over all of it: a player who walks into shot late is still
 * in several, and the backend then picks the frame that shows the most players. */
export const FRAMES = 12;
const MAX_W = 1280;
export const PICK_PLAYER = "Tap the player to analyse.";
const FINDING = "Finding the players in your video...";
const FETCHING = "Fetching the video from YouTube to find the players...";
/** The whole lookup (drawing frames + the request) never keeps the page waiting longer. */
export const LOOKUP_TIMEOUT_MS = 30_000;
/** A link is probed (~10 s) and downloaded whole before frames exist: a 3-minute video took
 * longer than the 30 s limit, which looked like a hang. */
export const LINK_TIMEOUT_MS = 120_000;
const LOAD_MS = 10_000;   // a playable file decodes its first frame well within this
const SEEK_MS = 6_000;
export const TOO_LONG = "Finding the players took too long.";
export const CANT_READ = "Your browser can't read frames from this video (often an iPhone HEVC file).";
const SENDING = "Your browser can't read this video, so we're sending it to find the players";
export const CHOOSE = "Choose “Analyse anyway” or try again.";
export const NOBODY = "We couldn't spot a player in your video.";
export const NOBODY_CHOOSE = "Choose “Analyse anyway” or pick another video.";

/** Rejects with `message` if `promise` hasn't settled within `ms`. */
export function withTimeout<T>(promise: Promise<T>, ms: number, message: string): Promise<T> {
  return new Promise<T>((ok, fail) => {
    const timer = setTimeout(() => fail(new Error(message)), ms);
    promise.then((v) => { clearTimeout(timer); ok(v); }, (e) => { clearTimeout(timer); fail(e); });
  });
}

/** The next `name` event on `target`; rejects on its "error" event or after `ms`. A video the
 * browser can't decode (Chrome and iPhone HEVC) reports its length but never fires
 * loadeddata or seeked, which used to leave the picker waiting forever. */
export function nextEvent(target: EventTarget, name: string, ms: number, message: string): Promise<void> {
  return new Promise<void>((ok, fail) => {
    const done = (error?: Error) => {
      clearTimeout(timer);
      target.removeEventListener(name, onEvent);
      target.removeEventListener("error", onError);
      if (error) fail(error);
      else ok();
    };
    const onEvent = () => done();
    const onError = () => done(new Error(message));
    const timer = setTimeout(() => done(new Error(message)), ms);
    target.addEventListener(name, onEvent);
    target.addEventListener("error", onError);
  });
}

/** `count` times spread evenly over the whole video, from near the start to near the end. */
export function frameTimes(duration: number, count = FRAMES): number[] {
  return Array.from({ length: count }, (_, i) => Number((((i + 0.5) / count) * duration).toFixed(3)));
}

/** Grab `count` JPEG frames spread over a local video, with their times in seconds. */
async function drawFrames(src: string, duration: number, signal: AbortSignal, count = FRAMES): Promise<{ time: number; blob: Blob }[]> {
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.preload = "auto";
  try {
    const loaded = nextEvent(video, "loadeddata", LOAD_MS, CANT_READ);   // listen before loading
    video.src = src;
    video.load();
    await loaded;
    if (!video.videoWidth) throw new Error(CANT_READ);
    const scale = Math.min(1, MAX_W / video.videoWidth);
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    const out = [];
    for (const time of frameTimes(duration, count)) {
      if (signal.aborted) throw signal.reason ?? new Error(TOO_LONG);
      const seeked = nextEvent(video, "seeked", SEEK_MS, CANT_READ);
      video.currentTime = time;
      await seeked;
      canvas.getContext("2d")!.drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise<Blob | null>((ok) => canvas.toBlob(ok, "image/jpeg", 0.8));
      if (blob) out.push({ time, blob });
    }
    return out;
  } finally {
    video.removeAttribute("src");
    video.load();
  }
}

/** Whether a frame-grab failure means "this browser can't decode the file", which the
 * server can still read with ffmpeg (an iPhone HEVC .MOV in Chrome without an HEVC decoder). */
export function serverCanRead(error: Error): boolean {
  return error.message === CANT_READ;
}

/** Send the whole video for the server to read its frames (XHR, for upload progress). The
 * 30 s answer limit starts once the upload is done; the upload itself can take a while. */
export function uploadForPlayers(file: File, kind: string, signal: AbortSignal, onProgress: (f: number) => void): Promise<Found> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const stop = () => { clearTimeout(timer); xhr.abort(); reject(signal.reason ?? new Error(TOO_LONG)); };
    if (signal.aborted) return stop();
    signal.addEventListener("abort", stop, { once: true });
    xhr.open("POST", playersEndpoint());
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
    xhr.upload.onload = () => {
      onProgress(1);
      timer = setTimeout(() => { xhr.abort(); reject(new Error(TOO_LONG)); }, LOOKUP_TIMEOUT_MS);
    };
    xhr.onload = () => {
      clearTimeout(timer);
      signal.removeEventListener("abort", stop);
      const data = xhr.response ?? {};
      if (xhr.status >= 200 && xhr.status < 300) return resolve(data as Found);
      // Our route answers {error}; FastAPI, reached directly, answers {detail}.
      reject(new Error(data.error ?? (typeof data.detail === "string" ? data.detail : "Couldn't look for players.")));
    };
    xhr.onerror = () => { clearTimeout(timer); reject(new Error("The upload failed. Check your connection and try again.")); };
    const body = new FormData();
    body.append("kind", kind);
    body.append("video", file);
    xhr.send(body);
  });
}

async function findPlayers(body: FormData, signal: AbortSignal): Promise<Found> {
  const res = await fetch("/api/players/detect", { method: "POST", body, signal });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error ?? "Couldn't look for players.");
  return data as Found;
}

/** The browser console's line for one lookup, so a slow one shows where its time went. */
export function lookupLog(s: { grabMs: number | null; frames: number; bytes: number; requestMs: number; found: Pick<Found, "candidates" | "timing" | "frames"> }): string {
  const t = s.found.timing ?? {};
  const grab = s.grabMs === null ? "" : `drew ${s.frames} frames (${Math.round(s.bytes / 1024)} KB) in ${(s.grabMs / 1000).toFixed(2)} s, `;
  const people = s.found.frames?.map((f) => `${f.time.toFixed(1)}s:${f.people}`).join(" ") ?? "";
  return `[players] ${grab}answer in ${(s.requestMs / 1000).toFixed(2)} s (Next.js ${t.next_s ?? "?"} s, backend ${t.total_s ?? "?"} s, detect ${t.seconds ?? "?"} s); `
    + `people per frame ${people || "-"}; ${s.found.candidates.length} players`;
}

/** What blocks the submit button. "Analyse anyway" is on screen whenever something does
 * (looking, a failure, nobody found), so the form can never be stuck. */
export function pickerProblem(s: { finding: boolean; failed: string | null; skipped: boolean; nobody?: boolean; asking: boolean; chosen: boolean }): string | null {
  if (s.skipped) return null;
  if (s.finding) return FINDING;
  if (s.failed) return CHOOSE;
  if (s.nobody) return NOBODY_CHOOSE;
  return s.asking && !s.chosen ? PICK_PLAYER : null;
}

const pct = (v: number) => `${(v * 100).toFixed(2)}%`;

export type View = "hidden" | "nobody" | "one" | "pick";

/** What to show for an answer, by how many players were found: nobody -> say so and offer
 * "Analyse anyway"; one -> analyse them (Change player opens the picker); two or more -> ask. */
export function pickerView(found: Pick<Found, "candidates" | "others" | "available"> | null, open: boolean): View {
  if (!found || found.available === false) return "hidden";
  const n = found.candidates.length;
  if (n === 0) return open && found.others?.length ? "pick" : "nobody";
  return n > 1 || open ? "pick" : "one";
}

/** Whether the user has to tap someone before submitting. */
export function needsChoice(found: Pick<Found, "candidates" | "others" | "available"> | null, open: boolean): boolean {
  return pickerView(found, open) === "pick";
}

const WHY: Record<string, string> = { still: "barely moves", far: "far from the table", small: "far away", more: "also seen" };

export function PlayerPicker({ previewUrl, duration, file = null, unreadable = false, link, kind, onProblem, jobId, onChoice }: {
  /** The chosen file's object URL and length, once the preview has loaded. */
  previewUrl: string | null;
  duration: number | null;
  /** The chosen file, sent whole when the browser can't read its frames (`unreadable`: the
   * preview itself failed to load). */
  file?: File | null;
  unreadable?: boolean;
  /** A valid YouTube link, when that is the input instead. */
  link: string | null;
  kind: "breakdown" | "match" | "coach";
  onProblem: (problem: string | null) => void;
  /** "Change player" on a result: look in that job's stored video and always ask. */
  jobId?: string;
  onChoice?: (choice: { time: number; box: Box }) => void;
}) {
  const [found, setFound] = useState<Found | null>(null);
  const [finding, setFinding] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const [skipped, setSkipped] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [choice, setChoice] = useState<Choice | null>(null);
  const [open, setOpen] = useState(false);
  const [everyone, setEveryone] = useState(false);
  const [sending, setSending] = useState<number | null>(null);   // upload progress, 0-1
  // The video kept on the server for the job; survives "Analyse anyway", so it isn't sent twice.
  const [staged, setStaged] = useState<string | null>(null);
  const lookupRef = useRef<AbortController | null>(null);

  // Look for players whenever the video changes (or on "Try again"). Every step has a time
  // limit; leaving, changing the video or giving up aborts the request, and the backend stops.
  useEffect(() => {
    setFound(null);
    setChoice(null);
    setOpen(false);
    setEveryone(false);
    setFailed(null);
    setSkipped(false);
    setFinding(false);
    setSending(null);
    setStaged(null);
    if (!(previewUrl && duration) && !(file && unreadable) && !link && !jobId) return;
    const controller = new AbortController();
    lookupRef.current = controller;
    let stale = false;
    setFinding(true);
    const lookup = async (body: FormData, grabMs: number | null, sent = { frames: 0, bytes: 0 }) => {
      body.append("kind", kind);
      const asked = performance.now();
      const found = await findPlayers(body, controller.signal);
      console.info(lookupLog({ grabMs, ...sent, requestMs: performance.now() - asked, found }));
      return found;
    };
    const fromFrames = async () => {
      const started = performance.now();
      const frames = await drawFrames(previewUrl!, duration!, controller.signal);
      const grabMs = performance.now() - started;
      const body = new FormData();
      frames.forEach((f, i) => body.append("frames", new File([f.blob], `frame${i}.jpg`, { type: "image/jpeg" })));
      body.append("times", frames.map((f) => f.time).join(","));
      body.append("grab_ms", String(Math.round(grabMs)));
      return lookup(body, grabMs, { frames: frames.length, bytes: frames.reduce((n, f) => n + f.blob.size, 0) });
    };
    const upload = async () => {
      // The server reads the frames with ffmpeg instead, and keeps the video for the job.
      // Its own limits apply (uploadForPlayers): a big video can take a while to go up.
      setSending(0);
      const asked = performance.now();
      const found = await uploadForPlayers(file!, kind, controller.signal, setSending);
      console.info(`[players] sent the whole video (${Math.round(file!.size / 1e6)} MB): `
        + lookupLog({ grabMs: null, frames: 0, bytes: 0, requestMs: performance.now() - asked, found }).slice(10));
      return found;
    };
    const run = async (): Promise<Found> => {
      if (jobId) {
        const body = new FormData();
        body.append("job", jobId);
        return withTimeout(lookup(body, null), LOOKUP_TIMEOUT_MS, TOO_LONG);
      }
      if (file && unreadable) return upload();   // the preview itself failed to load
      if (previewUrl && duration) {
        try {
          return await withTimeout(fromFrames(), LOOKUP_TIMEOUT_MS, TOO_LONG);
        } catch (e) {
          if (file && serverCanRead(e as Error)) return upload();
          throw e;
        }
      }
      const body = new FormData();
      body.append("url", link!);
      return withTimeout(lookup(body, null), LINK_TIMEOUT_MS, TOO_LONG);
    };
    const timer = setTimeout(() => {
      run()
        .then((r) => {
          if (stale) return;
          setFound(r);
          setStaged(r.staged ?? null);
          // One player: theirs is the only answer. Two or more: always ask (being nearest the
          // camera most often picked the partner on montages).
          const only = r.candidates.length === 1 ? r.candidates[0] : null;
          setChoice(only ? { id: only.id, time: only.time, box: only.box } : null);
        })
        .catch((e: Error) => {
          if (stale) return;
          controller.abort();   // a timeout: stop the request so the backend stops too
          setFailed(e.name === "AbortError" ? TOO_LONG : e.message || "Couldn't look for players.");
        })
        .finally(() => { if (!stale) { setFinding(false); setSending(null); } });
    }, link ? 600 : 0);   // let a pasted link settle before downloading it
    return () => { stale = true; clearTimeout(timer); controller.abort(); };
  }, [previewUrl, duration, file, unreadable, link, kind, jobId, attempt]);

  const view = pickerView(found, open || !!jobId);
  const asking = view === "pick";
  const problem = pickerProblem({ finding, failed, skipped, nobody: view === "nobody", asking, chosen: !!choice });
  useEffect(() => { onProblem(problem); }, [problem, onProblem]);
  useEffect(() => () => onProblem(null), [onProblem]);   // unmounted: nothing to wait for

  // Stop whatever is still running (a whole video going up, say) before the form sends its own.
  const giveUp = () => { lookupRef.current?.abort(); setSkipped(true); setFinding(false); setFailed(null); setFound(null); setChoice(null); };
  // A result page's "Change player" has no form to submit, so nothing to analyse anyway.
  const anyway = jobId ? null : (
    <button type="button" onClick={giveUp} className="text-sm font-bold text-accent hover:text-accent-hot">
      Analyse anyway (auto-pick)
    </button>
  );

  const keep = staged && <input type="hidden" name="staged" value={staged} />;
  const hidden = (
    <>
      {choice && <input type="hidden" name="player_time" value={choice.time} />}
      {choice && <input type="hidden" name="player_box" value={choice.box.join(",")} />}
      {keep}
    </>
  );
  if (skipped) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-line bg-panel px-4 py-3">
        {keep}
        <p className="flex-1 text-sm text-muted">We&apos;ll pick the player automatically.</p>
        <button type="button" onClick={() => setAttempt((n) => n + 1)} className="text-sm font-bold text-accent hover:text-accent-hot">
          Pick a player
        </button>
      </div>
    );
  }
  if (finding) {
    const what = sending !== null
      ? (sending < 1 ? `${SENDING}... ${Math.round(sending * 100)}%` : `${FINDING}`)
      : link && !previewUrl && !jobId ? FETCHING : FINDING;
    return (
      <div className="stripes space-y-2 rounded-xl border border-line bg-panel px-4 py-3">
        <div className="flex items-center gap-3">
          <p aria-live="polite" className="flex-1 text-sm text-muted">{what}</p>
          {anyway}
        </div>
        {sending !== null && sending < 1 && (
          <div role="progressbar" aria-label="Sending the video" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(sending * 100)}
               className="h-1.5 overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full bg-accent" style={{ width: `${sending * 100}%` }} />
          </div>
        )}
      </div>
    );
  }
  if (failed) {
    return (
      <div role="alert" className="space-y-2 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3">
        <p className="text-sm text-red-100">{failed} You can analyse anyway (we pick the player nearest the camera most often), or try again.</p>
        <div className="flex gap-5">
          {anyway}
          <button type="button" onClick={() => setAttempt((n) => n + 1)} className="text-sm font-bold text-muted hover:text-white">
            Try again
          </button>
        </div>
      </div>
    );
  }
  if (!found || view === "hidden") return null;
  const others = found.others ?? [];
  const showOthers = everyone || found.candidates.length === 0;
  const people = showOthers ? [...found.candidates, ...others] : found.candidates;
  const chosen = choice ? people.find((c) => c.id === choice.id) : undefined;
  const showEveryone = () => { setEveryone(true); setOpen(true); };

  if (view === "nobody") {
    return (
      <div role="alert" className="space-y-2 rounded-xl border border-line bg-panel px-4 py-3">
        {hidden}
        <p className="text-sm">
          {NOBODY} <span className="text-muted">Film with your whole body in view, or analyse anyway and we&apos;ll look through the whole video.</span>
        </p>
        <div className="flex flex-wrap gap-5">
          {anyway}
          {others.length > 0 && (
            <button type="button" onClick={showEveryone} className="text-sm font-bold text-muted hover:text-white">
              Show everyone we saw ({others.length})
            </button>
          )}
        </div>
      </div>
    );
  }

  if (view === "one") {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-line bg-panel p-2 pr-4">
        {hidden}
        {chosen && <img src={chosen.thumb} alt="" className="h-14 w-auto rounded-lg" />}
        <p aria-live="polite" className="flex-1 text-sm">Analysing this player</p>
        <button type="button" onClick={() => setOpen(true)} className="text-sm font-bold text-accent hover:text-accent-hot">
          Change player
        </button>
      </div>
    );
  }

  const select = (c: Candidate, time = c.time, box = c.box) => {
    setChoice({ id: c.id, time, box });
    onChoice?.({ time, box });
  };
  return (
    <fieldset className="space-y-3">
      {hidden}
      <legend className="headline mb-1 text-2xl">{kind === "breakdown" ? "Which player should we analyse?" : "Which one is you?"}</legend>
      <p className="text-sm text-muted">
        {found.candidates.length > 1 ? `We see ${found.candidates.length} players. ` : ""}
        {kind === "breakdown" ? "Tap the one to break down." : "Tap yourself so we analyse the right one."}
      </p>
      {found.frame && (
        <div className="relative overflow-hidden rounded-2xl border border-line bg-black">
          <img src={found.frame.image} alt="A frame from your video" className="block w-full" />
          {found.frame.boxes.map(({ id, box }) => {
            const c = people.find((x) => x.id === id);
            if (!c) return null;
            const on = choice?.id === id;
            return (
              <button
                key={id} type="button" aria-pressed={on} aria-label={`Player ${id + 1}`}
                onClick={() => select(c, found.frame!.time, box)}
                style={{ left: pct(box[0]), top: pct(box[1]), width: pct(box[2] - box[0]), height: pct(box[3] - box[1]) }}
                className={`absolute rounded-lg border-2 ${on ? "border-accent bg-accent/20 shadow-[0_0_24px_color-mix(in_srgb,var(--accent-glow)_60%,transparent)]" : `${c.background ? "border-dashed border-white/50" : "border-white/80"} bg-white/5 hover:border-accent`}`}
              />
            );
          })}
        </div>
      )}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {people.map((c) => {
          const on = choice?.id === c.id;
          return (
            <button
              key={c.id} type="button" aria-pressed={on} onClick={() => select(c)}
              className={`relative shrink-0 overflow-hidden rounded-xl border-2 ${on ? "border-accent" : "border-line hover:border-white/40"}`}
            >
              <img src={c.thumb} alt={`Player ${c.id + 1}${c.background ? `, ${WHY[c.background] ?? "background"}` : ""}`} className={`h-24 w-auto ${c.background && !on ? "opacity-70" : ""}`} />
              {c.background && (
                <span className="absolute inset-x-0 bottom-0 bg-black/70 px-1 py-0.5 text-center text-[10px] font-semibold uppercase tracking-wide text-muted">
                  {WHY[c.background] ?? "background"}
                </span>
              )}
            </button>
          );
        })}
      </div>
      {!showOthers && others.length > 0 && (
        <button type="button" onClick={showEveryone} className="text-sm font-bold text-muted hover:text-white">
          Not here? Show everyone we saw ({others.length} more)
        </button>
      )}
      {!choice && <p role="alert" className="text-sm text-red-200">{PICK_PLAYER}</p>}
    </fieldset>
  );
}
