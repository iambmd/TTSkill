"""Find the players in a few frames of a clip, for "tap the player to analyze".

Each frame goes through the same person detector and plausibility rules as tracking
(pose._pose_candidates). People are grouped across frames by torso and thigh colours, and
spectators and other courts are dropped by size. The answer says whether a picker is needed:
one player, or a clear "nearest the camera" winner, needs no question."""
from __future__ import annotations

import base64
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from .identity import STRICT, signature, signature_distance

MAX_CANDIDATES = 4    # a table has 2 (doubles 4) players; more boxes would be spectators
MIN_SEEN = 1 / 3      # share of frames a player appears in; passers-by appear once
MIN_SIZE = 0.3        # torso vs the biggest candidate's; smaller is another court or a spectator
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


def group(detections: list[Detection], n_frames: int) -> dict:
    """Pure grouping and decision, given every frame's detections.

    Returns {"players": [[Detection, ...], ...] best first, "suggested": index or None,
    "decisive": bool}."""
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
    size = [float(np.median([d.torso for d in pl])) for pl in players]
    biggest = max(size, default=0.0)
    keep = [k for k, pl in enumerate(players)
            if len({d.frame for d in pl}) >= max(1, MIN_SEEN * n_frames) and size[k] >= MIN_SIZE * biggest]
    keep = sorted(keep, key=lambda k: (-len(players[k]), -size[k]))[:MAX_CANDIDATES]
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
        return {"players": [], "suggested": None, "decisive": False, "near": []}
    order = sorted(range(len(kept)), key=lambda i: -near[i])
    top = near[order[0]]
    runner = near[order[1]] if len(order) > 1 else 0
    decisive = len(kept) == 1 or (frames_with >= 3 and top >= DECISIVE_SHARE * frames_with and top >= 2 * runner)
    return {"players": kept, "suggested": order[0], "decisive": bool(decisive),
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


def detect(frames: list[tuple[float, np.ndarray]], cancel: threading.Event | None = None,
           budget: float = BUDGET_S) -> dict:
    """frames: (time in s, BGR image). Returns the picker's data:
    {"candidates": [{id, time, box, thumb, seen, near}], "frame": {time, image, boxes},
     "suggested": id or None, "decisive": bool, "timing": {...}}.
    cancel: set when the browser disconnects; raises Cancelled at the next frame."""
    start = time.monotonic()   # before the imports: the first call pays ~1 s for them
    from .pose import QUARTERS, _pose_candidates

    landmarker, mp = _landmarker()
    loaded = time.monotonic() - start
    images = []
    detections: list[Detection] = []
    found: list[int] = []   # people per frame, for the log
    zoomed = 0
    for f, (_, image) in enumerate(frames):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        spent = time.monotonic() - start
        if spent > budget and f >= 2:
            break   # answer with the frames done so far rather than keep the page waiting
        h, w = image.shape[:2]
        if h > 720:   # the same working size as the seed and tracking
            image = cv2.resize(image, (round(w * 720 / h), 720))
            h, w = image.shape[:2]
        images.append(image)
        extra = QUARTERS if spent < budget / 2 else None
        zoomed += extra is not None
        people, _ = _pose_candidates(image, landmarker, mp, extra=extra)
        found.append(len(people))
        for p in people:
            torso = float(np.linalg.norm((p[[11, 12], :2].mean(0) - p[[23, 24], :2].mean(0)) * [w, h]))
            detections.append(Detection(f, box_of(p), torso, signature(image, p)))
    frames = frames[:len(images)]
    g = group(detections, len(frames))
    candidates = []
    for i, pl in enumerate(g["players"]):
        best = max(pl, key=lambda d: d.torso)   # the clearest (largest) view of this player
        candidates.append({"id": i, "time": round(frames[best.frame][0], 3),
                           "box": [round(v, 4) for v in best.box], "thumb": _thumb(images[best.frame], best.box),
                           "seen": round(len({d.frame for d in pl}) / len(frames), 2), "near": g["near"][i]})
    frame = None
    if g["players"]:
        # One frame that shows as many candidates as possible, for tapping.
        f = max(range(len(frames)), key=lambda f: (sum(any(d.frame == f for d in pl) for pl in g["players"]),
                                                     -f))
        image = images[f]
        if image.shape[1] > FRAME_W:
            image = cv2.resize(image, (FRAME_W, round(image.shape[0] * FRAME_W / image.shape[1])))
        frame = {"time": round(frames[f][0], 3), "image": _jpeg(image),
                 "boxes": [{"id": i, "box": [round(v, 4) for v in d.box]}
                           for i, pl in enumerate(g["players"]) for d in pl if d.frame == f]}
    timing = {"seconds": round(time.monotonic() - start, 2), "model_load_s": round(loaded, 2),
              "frames": len(images), "zoomed_frames": zoomed}
    return {"candidates": candidates, "frame": frame, "suggested": g["suggested"], "decisive": g["decisive"],
            "frames": [{"time": round(t, 3), "people": n} for (t, _), n in zip(frames, found)],
            "timing": timing}


def warm() -> None:
    """Load the model on this thread and run it once, so the first picker doesn't pay for it."""
    from . import pose  # noqa: F401  (the import alone is ~1 s)

    landmarker, mp = _landmarker()
    landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.zeros((256, 256, 3), np.uint8)))


def sample_frames(video: str, count: int = 6) -> list[tuple[float, np.ndarray]]:
    """Frames spread over a video on disk (pasted links), as the browser does for uploads."""
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = []
    for idx in ((np.arange(count) + .5) / count * max(n - 1, 1)).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if ok:
            out.append((float(idx / fps), frame))
    cap.release()
    return out
