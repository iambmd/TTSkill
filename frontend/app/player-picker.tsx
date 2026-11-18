"use client";

/**
 * "Which one is you?" When the chosen video shows more than one player, the analysis needs to
 * know who to follow. We draw a few frames from the file in the browser (no second upload),
 * ask /api/players/detect who is in them, and only ask when the answer isn't clear. The choice
 * goes with the job as hidden player_time and player_box fields.
 */
import { useEffect, useState } from "react";

type Box = [number, number, number, number];
type Candidate = { id: number; time: number; box: Box; thumb: string; seen: number; near: number };
type Found = {
  candidates: Candidate[];
  frame: { time: number; image: string; boxes: { id: number; box: Box }[] } | null;
  suggested: number | null;
  decisive: boolean;
};
type Choice = { id: number; time: number; box: Box };

const FRAMES = 6;
const MAX_W = 1280;
export const PICK_PLAYER = "Tap the player to analyse.";
const FINDING = "Finding the players in your video...";
/** The whole lookup (drawing frames + the request) never keeps the page waiting longer. */
export const LOOKUP_TIMEOUT_MS = 30_000;
const LOAD_MS = 10_000;   // a playable file decodes its first frame well within this
const SEEK_MS = 6_000;
export const TOO_LONG = "Finding the players took too long.";
export const CANT_READ = "Your browser can't read frames from this video (often an iPhone HEVC file).";
export const CHOOSE = "Choose “Analyse anyway” or try again.";

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
    for (let i = 0; i < count; i++) {
      if (signal.aborted) throw signal.reason ?? new Error(TOO_LONG);
      const time = ((i + 0.5) / count) * duration;
      const seeked = nextEvent(video, "seeked", SEEK_MS, CANT_READ);
      video.currentTime = time;
      await seeked;
      canvas.getContext("2d")!.drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise<Blob | null>((ok) => canvas.toBlob(ok, "image/jpeg", 0.8));
      if (blob) out.push({ time: Number(time.toFixed(3)), blob });
    }
    return out;
  } finally {
    video.removeAttribute("src");
    video.load();
  }
}

async function findPlayers(body: FormData, signal: AbortSignal): Promise<Found> {
  const res = await fetch("/api/players/detect", { method: "POST", body, signal });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error ?? "Couldn't look for players.");
  return data as Found;
}

/** What blocks the submit button. The "Analyse anyway" button is always on screen while a
 * lookup runs or after it fails, so the form can never be stuck. */
export function pickerProblem(s: { finding: boolean; failed: string | null; skipped: boolean; asking: boolean; chosen: boolean }): string | null {
  if (s.skipped) return null;
  if (s.finding) return FINDING;
  if (s.failed) return CHOOSE;
  return s.asking && !s.chosen ? PICK_PLAYER : null;
}

const pct = (v: number) => `${(v * 100).toFixed(2)}%`;

/** Auto first: ask only when there are 2+ players and the nearest-player vote isn't clear,
 * or when the user asked to change the automatic choice. */
export function needsChoice(found: Pick<Found, "candidates" | "decisive"> | null, open: boolean): boolean {
  return !!found && found.candidates.length > 1 && (!found.decisive || open);
}

export function PlayerPicker({ previewUrl, duration, link, kind, onProblem, jobId, onChoice }: {
  /** The chosen file's object URL and length, once the preview has loaded. */
  previewUrl: string | null;
  duration: number | null;
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

  // Look for players whenever the video changes (or on "Try again"). Every step has a time
  // limit; leaving, changing the video or giving up aborts the request, and the backend stops.
  useEffect(() => {
    setFound(null);
    setChoice(null);
    setOpen(false);
    setFailed(null);
    setSkipped(false);
    setFinding(false);
    if (!(previewUrl && duration) && !link && !jobId) return;
    const controller = new AbortController();
    let stale = false;
    setFinding(true);
    const run = async () => {
      const body = new FormData();
      body.append("kind", kind);
      if (jobId) {
        body.append("job", jobId);
      } else if (previewUrl && duration) {
        const frames = await drawFrames(previewUrl, duration, controller.signal);
        frames.forEach((f, i) => body.append("frames", new File([f.blob], `frame${i}.jpg`, { type: "image/jpeg" })));
        body.append("times", frames.map((f) => f.time).join(","));
      } else {
        body.append("url", link!);
      }
      return findPlayers(body, controller.signal);
    };
    const timer = setTimeout(() => {
      withTimeout(run(), LOOKUP_TIMEOUT_MS, TOO_LONG)
        .then((r) => {
          if (stale) return;
          setFound(r);
          const pick = r.decisive && r.suggested !== null ? r.candidates[r.suggested] : null;
          setChoice(pick ? { id: pick.id, time: pick.time, box: pick.box } : null);
        })
        .catch((e: Error) => {
          if (stale) return;
          controller.abort();   // a timeout: stop the request so the backend stops too
          setFailed(e.name === "AbortError" ? TOO_LONG : e.message || "Couldn't look for players.");
        })
        .finally(() => { if (!stale) setFinding(false); });
    }, link ? 600 : 0);   // let a pasted link settle before downloading it
    return () => { stale = true; clearTimeout(timer); controller.abort(); };
  }, [previewUrl, duration, link, kind, jobId, attempt]);

  const asking = needsChoice(found, open || !!jobId);
  const problem = pickerProblem({ finding, failed, skipped, asking, chosen: !!choice });
  useEffect(() => { onProblem(problem); }, [problem, onProblem]);
  useEffect(() => () => onProblem(null), [onProblem]);   // unmounted: nothing to wait for

  const giveUp = () => { setSkipped(true); setFinding(false); setFailed(null); setFound(null); setChoice(null); };
  const anyway = (
    <button type="button" onClick={giveUp} className="text-sm font-bold text-accent hover:text-accent-hot">
      Analyse anyway (auto-pick)
    </button>
  );

  const hidden = choice && (
    <>
      <input type="hidden" name="player_time" value={choice.time} />
      <input type="hidden" name="player_box" value={choice.box.join(",")} />
    </>
  );
  if (skipped) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-line bg-panel px-4 py-3">
        <p className="flex-1 text-sm text-muted">We&apos;ll pick the player automatically.</p>
        <button type="button" onClick={() => setAttempt((n) => n + 1)} className="text-sm font-bold text-accent hover:text-accent-hot">
          Pick a player
        </button>
      </div>
    );
  }
  if (finding) {
    return (
      <div className="stripes flex items-center gap-3 rounded-xl border border-line bg-panel px-4 py-3">
        <p aria-live="polite" className="flex-1 text-sm text-muted">{FINDING}</p>
        {anyway}
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
  if (!found || found.candidates.length === 0) return null;
  const chosen = choice ? found.candidates.find((c) => c.id === choice.id) : undefined;

  if (!asking) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-line bg-panel p-2 pr-4">
        {hidden}
        {chosen && <img src={chosen.thumb} alt="" className="h-14 w-auto rounded-lg" />}
        <p className="flex-1 text-sm text-muted">We&apos;ll analyse this player.</p>
        {found.candidates.length > 1 && (
          <button type="button" onClick={() => setOpen(true)} className="text-sm font-bold text-accent hover:text-accent-hot">
            Change
          </button>
        )}
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
        {kind === "breakdown" ? "We see more than one player. Tap the one to break down." : "We see more than one player. Tap yourself so we analyse the right one."}
      </p>
      {found.frame && (
        <div className="relative overflow-hidden rounded-2xl border border-line bg-black">
          <img src={found.frame.image} alt="A frame from your video" className="block w-full" />
          {found.frame.boxes.map(({ id, box }) => {
            const c = found.candidates.find((x) => x.id === id);
            if (!c) return null;
            const on = choice?.id === id;
            return (
              <button
                key={id} type="button" aria-pressed={on} aria-label={`Player ${id + 1}`}
                onClick={() => select(c, found.frame!.time, box)}
                style={{ left: pct(box[0]), top: pct(box[1]), width: pct(box[2] - box[0]), height: pct(box[3] - box[1]) }}
                className={`absolute rounded-lg border-2 ${on ? "border-accent bg-accent/20 shadow-[0_0_24px_rgb(255_107_44/0.6)]" : "border-white/80 bg-white/5 hover:border-accent"}`}
              />
            );
          })}
        </div>
      )}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {found.candidates.map((c) => {
          const on = choice?.id === c.id;
          return (
            <button
              key={c.id} type="button" aria-pressed={on} onClick={() => select(c)}
              className={`shrink-0 overflow-hidden rounded-xl border-2 ${on ? "border-accent" : "border-line hover:border-white/40"}`}
            >
              <img src={c.thumb} alt={`Player ${c.id + 1}`} className="h-24 w-auto" />
            </button>
          );
        })}
      </div>
      {!choice && <p role="alert" className="text-sm text-red-200">{PICK_PLAYER}</p>}
    </fieldset>
  );
}
