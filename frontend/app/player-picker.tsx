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

/** Grab `count` JPEG frames spread over a local video, with their times in seconds. */
async function drawFrames(src: string, duration: number, count = FRAMES): Promise<{ time: number; blob: Blob }[]> {
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.preload = "auto";
  video.src = src;
  await new Promise<void>((ok, fail) => {
    video.onloadeddata = () => ok();
    video.onerror = () => fail(new Error("can't read the video"));
  });
  const scale = Math.min(1, MAX_W / video.videoWidth);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  const out = [];
  for (let i = 0; i < count; i++) {
    const time = ((i + 0.5) / count) * duration;
    await new Promise<void>((ok) => {
      video.onseeked = () => ok();
      video.currentTime = time;
    });
    canvas.getContext("2d")!.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((ok) => canvas.toBlob(ok, "image/jpeg", 0.8));
    if (blob) out.push({ time: Number(time.toFixed(3)), blob });
  }
  video.removeAttribute("src");
  video.load();
  return out;
}

async function findPlayers(body: FormData): Promise<Found> {
  const res = await fetch("/api/players/detect", { method: "POST", body });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error ?? "Couldn't look for players.");
  return data as Found;
}

const pct = (v: number) => `${(v * 100).toFixed(2)}%`;

/** Auto first: ask only when there are 2+ players and the nearest-player vote isn't clear,
 * or when the user asked to change the automatic choice. */
export function needsChoice(found: Pick<Found, "candidates" | "decisive"> | null, open: boolean): boolean {
  return !!found && found.candidates.length > 1 && (!found.decisive || open);
}

export function PlayerPicker({ previewUrl, duration, link, kind, onProblem }: {
  /** The chosen file's object URL and length, once the preview has loaded. */
  previewUrl: string | null;
  duration: number | null;
  /** A valid YouTube link, when that is the input instead. */
  link: string | null;
  kind: "breakdown" | "match" | "coach";
  onProblem: (problem: string | null) => void;
}) {
  const [found, setFound] = useState<Found | null>(null);
  const [finding, setFinding] = useState(false);
  const [choice, setChoice] = useState<Choice | null>(null);
  const [open, setOpen] = useState(false);

  // Look for players whenever the video changes. A failure just leaves the choice to the
  // analysis (the person nearest the camera most often), as before this picker existed.
  useEffect(() => {
    setFound(null);
    setChoice(null);
    setOpen(false);
    if (!(previewUrl && duration) && !link) return;
    let stale = false;
    setFinding(true);
    const run = async () => {
      const body = new FormData();
      body.append("kind", kind);
      if (previewUrl && duration) {
        const frames = await drawFrames(previewUrl, duration);
        frames.forEach((f, i) => body.append("frames", new File([f.blob], `frame${i}.jpg`, { type: "image/jpeg" })));
        body.append("times", frames.map((f) => f.time).join(","));
      } else {
        body.append("url", link!);
      }
      return findPlayers(body);
    };
    const timer = setTimeout(() => {
      run()
        .then((r) => {
          if (stale) return;
          setFound(r);
          const pick = r.decisive && r.suggested !== null ? r.candidates[r.suggested] : null;
          setChoice(pick ? { id: pick.id, time: pick.time, box: pick.box } : null);
        })
        .catch(() => { if (!stale) setFound(null); })
        .finally(() => { if (!stale) setFinding(false); });
    }, link ? 600 : 0);   // let a pasted link settle before downloading it
    return () => { stale = true; clearTimeout(timer); };
  }, [previewUrl, duration, link, kind]);

  const asking = needsChoice(found, open);
  const problem = finding ? FINDING : asking && !choice ? PICK_PLAYER : null;
  useEffect(() => { onProblem(problem); }, [problem, onProblem]);

  const hidden = choice && (
    <>
      <input type="hidden" name="player_time" value={choice.time} />
      <input type="hidden" name="player_box" value={choice.box.join(",")} />
    </>
  );
  if (finding) {
    return <p aria-live="polite" className="stripes rounded-xl border border-line bg-panel px-4 py-3 text-sm text-muted">{FINDING}</p>;
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

  const select = (c: Candidate, time = c.time, box = c.box) => setChoice({ id: c.id, time, box });
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
