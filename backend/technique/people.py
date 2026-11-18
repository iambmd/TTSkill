"""Find the players in frames spread over a clip, for "tap the player to analyze".

Each frame goes through the same person detector and plausibility rules as tracking
(pose._pose_candidates); two skeletons of one person in a frame are merged. People are
grouped across frames by torso and thigh colours, and passers-by, spectators and other
courts are dropped. The answer gives one thumbnail per distinct person and the frame that
shows the most of them."""
from __future__ import annotations

import base64
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from .identity import STRICT, signature, signature_distance

MAX_CANDIDATES = 4    # a table has 2 (doubles 4) players; more boxes would be spectators
FRAMES = 12           # frames looked at, spread over the whole video
# A passer-by is in one frame. A player who comes into shot late is only in the last few, so
# this is a count, not a share of the frames (a third of 12 dropped a player seen in 3).
MIN_SIGHTINGS = 2
MIN_SIZE = 0.3        # torso vs the biggest candidate's; smaller is another court or a spectator
# Background people (Change player still shows them; auto mode ignores them):
# - still: across their sightings the body box moves less than this (median abs deviation in box
#   heights). Players measured 0.083-0.594 on the four samples; a table leg traced as a body
#   0.045, a static figure 0.011.
STILL = 0.05
# - far from the table: further from its side than this many table widths, in every frame
#   where a table is found (only blue/green tops are found; grey ones never count against anyone).
FAR_TABLE = 0.5
MAX_OTHERS = 4
# Two skeletons in one frame whose shoulders are this close (x the larger torso) are one person:
# a zoomed crop re-finds someone already found (measured 0.02-0.11; different people >= 1.8).
SAME_PERSON = 0.25
DECISIVE_SHARE = 2 / 3  # nearest in this share of frames, and twice as often as anyone else
THUMB_H = 160
FRAME_W = 960
# Seconds of detection before answering with what was found: the zoomed quarters stop after
# half of it, frames after all of it. 6 frames measured 1.5-1.7 s in-process, 1.6-3.5 s over HTTP.
BUDGET_S = 8.0

_LOCAL = threading.local()   # one loaded model per worker thread (MediaPipe objects aren't thread-safe)


class Cancelled(Exception):
    """The browser went away, so nobody wants the answer."""


def _landmarker():
    """The pose model, loaded once per thread and reused (loading took up to 0.3 s a request)."""
    lmk = getattr(_LOCAL, "landmarker", None)
    if lmk is None:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        from .pose import model_path

        opts = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path())),
            running_mode=vision.RunningMode.IMAGE, num_poses=3,
            min_pose_detection_confidence=0.4, min_tracking_confidence=0.4,
        )
        lmk = _LOCAL.landmarker = vision.PoseLandmarker.create_from_options(opts)
        _LOCAL.mp = mp
    return lmk, _LOCAL.mp


@dataclass
class Detection:
    frame: int            # index into the frames
    box: tuple[float, float, float, float]   # normalised x0, y0, x1, y1
    torso: float          # torso length in pixels
    look: np.ndarray      # identity.signature


def box_of(lm: np.ndarray) -> tuple[float, float, float, float]:
    """Normalised box around the visible landmarks, padded a little for the head and feet."""
    seen = lm[lm[:, 3] >= .3, :2] if (lm[:, 3] >= .3).sum() >= 4 else lm[:, :2]
    x0, y0 = seen.min(axis=0)
    x1, y1 = seen.max(axis=0)
    pw, ph = .1 * (x1 - x0), .08 * (y1 - y0)
    return (float(np.clip(x0 - pw, 0, 1)), float(np.clip(y0 - 1.5 * ph, 0, 1)),
            float(np.clip(x1 + pw, 0, 1)), float(np.clip(y1 + ph, 0, 1)))


def _torso(p: np.ndarray, w: int, h: int) -> float:
    return float(np.linalg.norm((p[[11, 12], :2].mean(0) - p[[23, 24], :2].mean(0)) * [w, h]))


def _thighs(p: np.ndarray, w: int, h: int) -> tuple[float, float]:
    """How far the knees sit below the hips, and how long the thighs are, in torso lengths."""
    torso = max(_torso(p, w, h), 1.0)
    d = (p[[25, 26], :2] - p[[23, 24], :2]) * [w, h]
    return float(d[:, 1].mean()) / torso, float(np.linalg.norm(d, axis=1).mean()) / torso


def lying(p: np.ndarray, w: int, h: int) -> bool:
    """A body traced over the table's legs: long thighs that don't go down. On the montage's
    arched table bases these measured knee drop -1.7 to 0.15, thighs 0.77-1.83 torsos; real
    players stand (drop >= 0.3), and misfits on real people have short thighs (0.33-0.43)."""
    drop, thigh = _thighs(p, w, h)
    return drop < 0.3 and thigh > 0.6


def one_per_person(people: list[np.ndarray], w: int, h: int) -> list[np.ndarray]:
    """Drop the second skeleton of a person found twice in one frame (a zoomed quarter often
    re-finds a near player as a partial body). An upright skeleton beats a sprawled one, then
    the more complete one stays."""
    torso = lambda p: _torso(p, w, h)

    def inside(a: tuple, b: tuple) -> float:
        """Share of box a that lies inside box b."""
        iw = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
        ih = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
        return iw * ih / max((a[2] - a[0]) * (a[3] - a[1]), 1e-9)

    kept: list[np.ndarray] = []
    for p in sorted(people, key=lambda p: (_thighs(p, w, h)[0] < 0.3, -float(p[[11, 12, 23, 24, 25, 26, 27, 28], 3].sum()))):
        shoulders = p[[11, 12], :2].mean(0) * [w, h]
        same = any(np.linalg.norm(shoulders - q[[11, 12], :2].mean(0) * [w, h]) < SAME_PERSON * max(torso(p), torso(q))
                   # a skeleton wholly inside another's box (legs only, say): a far player stands
                   # further back, so their box reaches above the near one's
                   or inside(box_of(p), box_of(q)) >= 0.9 for q in kept)
        if not same:
            kept.append(p)
    return kept


def _merge_apart(players: list[list[Detection]]) -> list[list[Detection]]:
    """Join groups that are never in the same frame and match on colours: the greedy pass
    can split one person when a frame's best match was already taken."""
    merged = True
    while merged:
        merged = False
        for a in range(len(players)):
            for b in range(a + 1, len(players)):
                if {d.frame for d in players[a]} & {d.frame for d in players[b]}:
                    continue
                # Average, not closest pair: on montages the closest pair chained a white shirt
                # onto the teal user through one look-alike frame.
                if np.mean([signature_distance(x.look, y.look) for x in players[a] for y in players[b]]) < STRICT:
                    players[a] += players.pop(b)
                    merged = True
                    break
            if merged:
                break
    return players


def typical(pl: list[Detection]) -> Detection:
    """The sighting that looks most like the rest of its group (the biggest of those within
    0.05 of the best): the thumbnail and seed. The biggest alone was once a different person
    the grouping had let in."""
    if len(pl) < 3:
        return max(pl, key=lambda d: d.torso)
    mean = [np.mean([signature_distance(d.look, o.look) for o in pl if o is not d]) for d in pl]
    best = min(mean)
    return max((d for d, m in zip(pl, mean) if m <= best + 0.05), key=lambda d: d.torso)


def box_motion(pl: list[Detection]) -> float:
    """How much a person's body box changes across their sightings, in box heights."""
    b = np.array([d.box for d in pl])
    height = float(np.median(b[:, 3] - b[:, 1])) or 1.0
    return float(np.abs(b - np.median(b, axis=0)).mean() / height)


def _far_from_table(pl: list[Detection], tables: list | None) -> bool:
    """Further than FAR_TABLE table widths from the table's side in every frame it was found in."""
    if not tables:
        return False
    gaps = []
    for d in pl:
        t = tables[d.frame] if d.frame < len(tables) else None
        if t is None:
            continue
        x0, x1 = t[0], t[2]
        gaps.append(max(0.0, x0 - d.box[2], d.box[0] - x1) / max(x1 - x0, 1e-6))
    return bool(gaps) and min(gaps) > FAR_TABLE


def group(detections: list[Detection], n_frames: int, tables: list | None = None) -> dict:
    """Pure grouping and decision, given every frame's detections (and, when found, each
    frame's table as a normalised box, else None).

    Returns {"players": [[Detection, ...], ...] best first, "others": [(group, reason), ...]
    (background people: "small", "still" or "far"), "suggested": index or None, "decisive": bool}."""
    players: list[list[Detection]] = []
    for f in range(n_frames):
        taken: set[int] = set()
        for d in sorted((d for d in detections if d.frame == f), key=lambda d: -d.torso):
            dists = [(min(signature_distance(d.look, o.look) for o in pl), k)
                     for k, pl in enumerate(players) if k not in taken]
            best = min(dists, default=(1.0, -1))
            if best[0] < STRICT:
                players[best[1]].append(d)
                taken.add(best[1])
            else:
                players.append([d])
                taken.add(len(players) - 1)
    players = _merge_apart(players)
    size = [float(np.median([d.torso for d in pl])) for pl in players]
    seen = [k for k, pl in enumerate(players) if len({d.frame for d in pl}) >= min(MIN_SIGHTINGS, n_frames)]
    reason: dict[int, str] = {}
    for k in seen:
        if len(players[k]) >= 2 and box_motion(players[k]) < STILL:
            reason[k] = "still"
    near_table = [k for k in seen if k not in reason and not _far_from_table(players[k], tables)]
    if near_table:   # a misread "table" that everyone is far from rules nobody out
        reason.update({k: "far" for k in seen if k not in reason and k not in near_table})
    # Small next to the biggest player (not a still spectator near the camera): another court.
    biggest = max((size[k] for k in seen if k not in reason), default=0.0)
    reason.update({k: "small" for k in seen if k not in reason and size[k] < MIN_SIZE * biggest})
    keep = sorted((k for k in seen if k not in reason), key=lambda k: (-len(players[k]), -size[k]))
    others = [(players[k], reason.get(k, "more")) for k in
              keep[MAX_CANDIDATES:] + sorted(reason, key=lambda k: (-len(players[k]), -size[k]))][:MAX_OTHERS]
    keep = keep[:MAX_CANDIDATES]
    kept = [players[k] for k in keep]
    # Who is nearest the camera (biggest torso) in each frame with a kept player in it.
    near = [0] * len(kept)
    frames_with = 0
    for f in range(n_frames):
        here = [(d.torso, i) for i, pl in enumerate(kept) for d in pl if d.frame == f]
        if here:
            frames_with += 1
            near[max(here)[1]] += 1
    if not kept:
        return {"players": [], "others": others, "suggested": None, "decisive": False, "near": []}
    order = sorted(range(len(kept)), key=lambda i: -near[i])
    top = near[order[0]]
    runner = near[order[1]] if len(order) > 1 else 0
    decisive = len(kept) == 1 or (frames_with >= 3 and top >= DECISIVE_SHARE * frames_with and top >= 2 * runner)
    return {"players": kept, "others": others, "suggested": order[0], "decisive": bool(decisive),
            "near": [round(n / max(frames_with, 1), 2) for n in near]}


def _jpeg(image: np.ndarray, quality: int = 80) -> str:
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode() if ok else ""


def _thumb(frame: np.ndarray, box: tuple[float, float, float, float]) -> str:
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)
    crop = frame[y0:max(y1, y0 + 2), x0:max(x1, x0 + 2)]
    scale = THUMB_H / crop.shape[0]
    return _jpeg(cv2.resize(crop, (max(1, round(crop.shape[1] * scale)), THUMB_H)))


def spread_order(n: int) -> list[int]:
    """0, n/2, n/4, 3n/4, ...: frames in an order that covers the whole video early, so a
    budget cut still leaves frames from the start, middle and end (it used to keep only the first)."""
    order: list[int] = []
    j = 0
    while len(order) < n:
        v, f, k = 0.0, 0.5, j   # the j-th van der Corput number: 0, .5, .25, .75, .125, ...
        while k:
            v += f * (k & 1)
            k >>= 1
            f /= 2
        i = min(n - 1, int(v * n))
        if i not in order:
            order.append(i)
        j += 1
    return order


def detect(frames: list[tuple[float, np.ndarray]], cancel: threading.Event | None = None,
           budget: float = BUDGET_S) -> dict:
    """frames: (time in s, BGR image), in time order. Returns the picker's data:
    {"candidates": [{id, time, box, thumb, seen, near}], "frame": {time, image, boxes},
     "suggested": id or None, "decisive": bool, "frames": [{time, people}], "timing": {...}}.
    cancel: set when the browser disconnects; raises Cancelled at the next frame."""
    start = time.monotonic()   # before the imports: the first call pays ~1 s for them
    from .pose import QUARTERS, _pose_candidates

    landmarker, mp = _landmarker()
    loaded = time.monotonic() - start
    done: dict[int, tuple[np.ndarray, list[np.ndarray]]] = {}
    zoomed = 0
    for k, f in enumerate(spread_order(len(frames))):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        spent = time.monotonic() - start
        if spent > budget and k >= 2:
            break   # answer with the frames done so far rather than keep the page waiting
        image = frames[f][1]
        h, w = image.shape[:2]
        if h > 720:   # the same working size as the seed and tracking
            image = cv2.resize(image, (round(w * 720 / h), 720))
            h, w = image.shape[:2]
        extra = QUARTERS if spent < budget / 2 else None
        zoomed += extra is not None
        people, _ = _pose_candidates(image, landmarker, mp, extra=extra)
        done[f] = (image, one_per_person([p for p in people if not lying(p, w, h)], w, h))
    used = sorted(done)                       # back in time order
    frames = [frames[f] for f in used]
    images = [done[f][0] for f in used]
    detections: list[Detection] = []
    for i, f in enumerate(used):
        h, w = images[i].shape[:2]
        for p in done[f][1]:
            torso = float(np.linalg.norm((p[[11, 12], :2].mean(0) - p[[23, 24], :2].mean(0)) * [w, h]))
            detections.append(Detection(i, box_of(p), torso, signature(images[i], p)))
    g = group(detections, len(frames), [_table_box(im) for im in images])

    def card(i: int, pl: list[Detection], **extra) -> dict:
        best = typical(pl)
        return {"id": i, "time": round(frames[best.frame][0], 3), "box": [round(v, 4) for v in best.box],
                "thumb": _thumb(images[best.frame], best.box), "seen": round(len({d.frame for d in pl}) / len(frames), 2),
                **extra}

    candidates = [card(i, pl, near=g["near"][i]) for i, pl in enumerate(g["players"])]
    n = len(candidates)
    others = [card(n + j, pl, background=why) for j, (pl, why) in enumerate(g["others"])]
    everyone = g["players"] + [pl for pl, _ in g["others"]]
    frame = None
    if everyone:
        # The frame that shows the most players (then anyone), the biggest on a tie, for tapping.
        def shown(f: int) -> tuple[int, int, float]:
            here = [d for pl in g["players"] for d in pl if d.frame == f]
            return len(here), sum(d.frame == f for pl, _ in g["others"] for d in pl), sum(d.torso for d in here)
        f = max(range(len(frames)), key=shown)
        image = images[f]
        if image.shape[1] > FRAME_W:
            image = cv2.resize(image, (FRAME_W, round(image.shape[0] * FRAME_W / image.shape[1])))
        frame = {"time": round(frames[f][0], 3), "image": _jpeg(image),
                 "boxes": [{"id": i, "box": [round(v, 4) for v in d.box]}
                           for i, pl in enumerate(everyone) for d in pl if d.frame == f]}
    timing = {"seconds": round(time.monotonic() - start, 2), "model_load_s": round(loaded, 2),
              "frames": len(images), "zoomed_frames": zoomed}
    return {"candidates": candidates, "others": others, "frame": frame, "suggested": g["suggested"],
            "decisive": g["decisive"],
            "frames": [{"time": round(t, 3), "people": len(done[f][1])} for (t, _), f in zip(frames, used)],
            "timing": timing}


def _table_box(image: np.ndarray) -> tuple[float, float, float, float] | None:
    """The table top as a normalised box, when its colour is found (blue or green)."""
    from players.table import find_table

    t = find_table(image)
    if t is None:
        return None
    h, w = image.shape[:2]
    x, y, bw, bh = t["bbox"]
    return (x / w, y / h, (x + bw) / w, (y + bh) / h)


def warm() -> None:
    """Load the model on this thread and run it once, so the first picker doesn't pay for it."""
    from . import pose  # noqa: F401  (the import alone is ~1 s)

    landmarker, mp = _landmarker()
    landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.zeros((256, 256, 3), np.uint8)))


RALLY_SHARE = 0.75   # of the frames go inside rallies (players in shot and playing), the rest anywhere


def frame_times(duration: float, rallies: list[tuple[float, float]], count: int = FRAMES) -> list[float]:
    """When to look for players: most frames spread over the rallies the sound found, the
    rest over the whole video (so a player who is never in a heard rally still shows up)."""
    even = lambda n, a, b: [a + (i + .5) / n * (b - a) for i in range(n)]
    spans = [(max(0.0, a), min(duration, b)) for a, b in rallies if min(duration, b) > max(0.0, a)]
    total = sum(b - a for a, b in spans)
    if total < 3.0:   # no real rallies heard: spread over the whole video, as the browser does
        return [round(t, 3) for t in even(count, 0.0, duration)]
    n_rally = round(count * RALLY_SHARE)
    times = []
    for x in even(n_rally, 0.0, total):   # positions along the rallies laid end to end
        for a, b in spans:
            if x <= b - a:
                times.append(a + x)
                break
            x -= b - a
    times += even(count - n_rally, 0.0, duration)
    return sorted(round(t, 3) for t in times)


def grab_frame(video: str, t: float) -> np.ndarray | None:
    """One frame at `t` s, at most 720 px high, decoded by ffmpeg (any codec it reads: iPhone
    HEVC included, and rotation applied, as the browser shows it)."""
    import subprocess

    # 2 decoder threads each, 6 at once: 12 frames of IMG_8782 (1080p HEVC) in 1.0 s; ffmpeg's
    # default (a thread per core in every process) took 1.9-4.2 s.
    out = subprocess.run(["ffmpeg", "-v", "error", "-threads", "2", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1",
                          "-vf", "scale=-2:'min(720,ih)'", "-f", "image2pipe", "-c:v", "bmp", "-"],
                         check=True, capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR) if out else None


def sample_frames(video: str, count: int = FRAMES) -> list[tuple[float, np.ndarray]]:
    """Frames of a video on disk (a pasted link, a past job, an upload the browser couldn't
    read), at frame_times: the audio pass costs ~1 s on a 3.5-minute match."""
    from concurrent.futures import ThreadPoolExecutor

    from . import audio, media

    duration = float(media.probe(video)["duration"])
    try:
        rallies = [(r["start"], r["end"]) for r in audio.find_rallies(video)]
    except Exception:   # no usable sound: spread over the whole video
        rallies = []
    times = frame_times(duration, rallies, count)
    with ThreadPoolExecutor(max_workers=6) as pool:
        images = list(pool.map(lambda t: grab_frame(video, t), times))
    return [(t, im) for t, im in zip(times, images) if im is not None]


SOLO_MOMENTS = 16     # moments looked at for "Only me in the video", mostly inside rallies
PAIR_GAP = 0.2        # s between a moment's two frames: a stroke moves the arms a lot in that time
LIMBS = [13, 14, 15, 16, 25, 26, 27, 28]   # elbows, wrists, knees, ankles


def limb_motion(a: np.ndarray, b: np.ndarray, w: int, h: int) -> float:
    """How far the limbs moved between two skeletons of one person, in torso lengths."""
    torso = max(_torso(a, w, h), 1.0)
    return float(np.linalg.norm((a[LIMBS, :2] - b[LIMBS, :2]) * [w, h], axis=1).mean()) / torso


def most_active(video: str, moments: int = SOLO_MOMENTS) -> np.ndarray | None:
    """"Only me in the video": the tracker seed for the person who plays the most. At each
    moment two frames PAIR_GAP apart show who is moving; a person's activity is their limb
    motion summed over the video, so being there and playing both count. Each moment counts in
    proportion to the person's size next to the biggest person then: landmark jitter on a far
    body reads as motion (coach_demo's far partner outscored the near user 4.19 to 3.38), and
    whoever films themselves is the one nearer the camera. Background people (still, far from
    the table, tiny next to the biggest) only win when nobody else is seen.
    None when nobody is seen (the caller falls back to the usual seed)."""
    from concurrent.futures import ThreadPoolExecutor

    from . import audio, media
    from .pose import QUARTERS, _pose_candidates

    duration = float(media.probe(video)["duration"])
    try:
        rallies = [(r["start"], r["end"]) for r in audio.find_rallies(video)]
    except Exception:
        rallies = []
    times = frame_times(max(0.0, duration - PAIR_GAP), rallies, moments)
    with ThreadPoolExecutor(max_workers=6) as pool:
        firsts = list(pool.map(lambda t: grab_frame(video, t), times))
        seconds = list(pool.map(lambda t: grab_frame(video, t + PAIR_GAP), times))
    landmarker, mp = _landmarker()
    detections: list[Detection] = []
    activity: dict[int, float] = {}
    images: list[np.ndarray] = []
    for i, (a, b) in enumerate(zip(firsts, seconds)):
        if a is None:
            a = np.zeros((360, 640, 3), np.uint8)
        images.append(a)
        h, w = a.shape[:2]
        found = lambda im: one_per_person([p for p in _pose_candidates(im, landmarker, mp, extra=QUARTERS)[0]
                                           if not lying(p, w, h)], w, h)
        now = found(a)
        later = found(b) if b is not None and b.shape == a.shape else []
        for p in now:
            torso = _torso(p, w, h)
            d = Detection(i, box_of(p), torso, signature(a, p))
            shoulders = p[[11, 12], :2].mean(0) * [w, h]
            # The same person 0.2 s later: the skeleton whose shoulders are nearest (within a torso).
            match = min(later, key=lambda q: np.linalg.norm(q[[11, 12], :2].mean(0) * [w, h] - shoulders), default=None)
            moved = 0.0
            if match is not None and np.linalg.norm(match[[11, 12], :2].mean(0) * [w, h] - shoulders) < torso:
                moved = limb_motion(p, match, w, h)
            detections.append(d)
            activity[id(d)] = moved
    for i in range(len(images)):
        here = [d for d in detections if d.frame == i]
        biggest = max((d.torso for d in here), default=1.0)
        for d in here:
            activity[id(d)] *= d.torso / biggest
    g = group(detections, len(images), [_table_box(im) for im in images])
    pool = g["players"] or [pl for pl, _ in g["others"]]
    if not pool:
        return None
    best = max(pool, key=lambda pl: sum(activity[id(d)] for d in pl))
    clearest = typical(best)
    print(f"only me: following the person seen in {len({d.frame for d in best})}/{len(images)} moments, "
          f"activity {sum(activity[id(d)] for d in best):.2f} (others: "
          f"{[round(sum(activity[id(d)] for d in pl), 2) for pl in pool if pl is not best]})", flush=True)
    return clearest.look
