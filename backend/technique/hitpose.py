"""Pose where the strokes are: full rate around the player's best strokes, a few frames a
second elsewhere to keep hold of the right player. Coach's fast path.

The old Coach ran full-rate pose on the same 8 s window three times (pose summary, breakdown,
pro match) after scanning six candidate rallies at 4 fps through encoded proxies. Here:
1. scan: each candidate rally at 1 fps (is the player there, how big, red rubber near which
   wrist), from an ffmpeg pipe (no proxy file);
2. probe: in the best rallies, one decode each, pose on 3 frames around every stroke onset the
   sound found (-0.1, 0, +0.1 s) and at 2 fps between: how fast each wrist moves at each onset;
3. windows: full rate (30 fps) from HALF before to HALF after the fastest onsets only.
Each window is its own 30 fps PoseTrack, so the stroke tools (key_moments, swing_peaks,
wrist_speeds) work on it unchanged."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Iterator

import numpy as np

import timing

from . import pose

HALF = 0.6            # s of full-rate pose before and after a chosen stroke's onset
LOW_FPS = 2.0         # identity tracking between probes
SCAN_FPS = 1.0        # the look at each candidate rally
SCAN_S = 8.0          # ...over its first seconds (choose_window's span)
FPS = 30.0
CANDIDATES = 6        # busiest rallies scanned (as choose_window)
RALLIES = 3           # of those, the best ones are probed (in order, until ENOUGH fast strokes)
ENOUGH = 4            # full-rate windows for this many of the fastest strokes
PROBE = 0.1           # s: the probe frames sit this far before and after each onset
STROKE_SPEED = 5.0    # torso lengths/s: the bat wrist at the player's own hit. Measured on the
                      # samples: 6-16 at the user's strokes, 0-5 while the opponent hits.
SAME_STROKE = 0.25    # s: onsets this close are one stroke (a double onset, or hit + own bounce)


@dataclass
class HitWindow:
    hit: float                 # s in the video
    track: pose.PoseTrack      # 30 fps, times relative to the window start
    start: float               # s in the video where the window's track starts
    own: bool = False          # the followed player's stroke (their bat wrist peaks at the hit)
    peak: int | None = None    # frame index of that peak in `track`


@dataclass
class HitPose:
    windows: list[HitWindow] = field(default_factory=list)
    probes: list[dict] = field(default_factory=list)     # per onset: hit, left, right (speeds), seen
    scan: list[dict] = field(default_factory=list)       # per candidate rally: visible, height, paddle
    paddle: dict = field(default_factory=lambda: {"left": 0, "right": 0})
    rallies: list[dict] = field(default_factory=list)    # the rallies that were probed
    frames: int = 0                                      # pose frames run in total


def frames(video: str, start: float, end: float, fps: float = FPS, height: int = 720) -> Iterator[tuple[float, np.ndarray]]:
    """Decoded frames of [start, end) at `fps`, at most `height` px high, as (time, BGR)."""
    from .people import grab_frame

    first = grab_frame(video, start)
    if first is None:
        return
    h, w = first.shape[:2]
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{max(0.05, end - start):.3f}", "-i", str(video),
         "-vf", f"scale={w}:{h},fps={fps}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = w * h * 3
    i = 0
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield start + i / fps, np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            i += 1
    finally:
        proc.stdout.close()
        proc.kill()
        proc.wait()


def red_near_wrists(frame: np.ndarray, lm: np.ndarray) -> dict:
    """Red-rubber pixels around each wrist (pose.paddle_scores on one frame in memory)."""
    import cv2

    h, w = frame.shape[:2]
    if np.isnan(lm[:, 0]).all():
        return {"left": 0, "right": 0}
    xy = np.nan_to_num(lm[:, :2]) * [w, h]
    torso = np.linalg.norm((xy[11] + xy[12]) / 2 - (xy[23] + xy[24]) / 2)
    r = max(12, int(torso * 0.45))
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    red = (((hsv[..., 0] < 10) | (hsv[..., 0] > 170)) & (hsv[..., 1] > 110) & (hsv[..., 2] > 60))
    out = {}
    for side, wi in (("left", pose.L_WRIST), ("right", pose.R_WRIST)):
        x, y = xy[wi].astype(int)
        out[side] = int(red[max(0, y - r):y + r, max(0, x - r):x + r].sum())
    return out


def _follow(follower: pose.Follower, video: str, start: float, end: float, fps: float, cut: bool = True):
    """Track [start, end) at `fps`; the first frame is marked as a jump in time."""
    times, lms, worlds, shots = [], [], [], []
    for k, (t, frame) in enumerate(frames(video, start, end, fps)):
        arr, warr = follower.step(frame, cut=cut and k == 0)
        times.append(t)
        lms.append(arr)
        worlds.append(warr)
        shots.append(frame)
    return times, lms, worlds, shots


def scan(follower: pose.Follower, video: str, rally: dict) -> tuple[dict, dict]:
    """choose_window's look at one rally: share of frames with the player whole, their median
    height in the frame, red rubber near each wrist. Low rate."""
    start = max(0.0, rally["start"] - HALF)
    times, lms, worlds, shots = _follow(follower, video, start, min(rally["end"] + 0.8, start + SCAN_S), SCAN_FPS)
    if not times:
        return {"visible": 0.0, "height": 0.0, "frames": 0}, {"left": 0, "right": 0}
    tr = pose.make_track(times, lms, worlds, SCAN_FPS, shots[0].shape[1], shots[0].shape[0], {})
    whole = pose.whole_body(tr)
    heights = tr.lm[whole, :, 1].max(axis=1) - tr.lm[whole, :, 1].min(axis=1)
    paddle = {"left": 0, "right": 0}
    for frame, lm, ok in zip(shots, tr.lm, tr.valid):
        if ok:
            for side, v in red_near_wrists(frame, lm).items():
                paddle[side] += v
    return {"visible": float(whole.mean()), "height": float(np.median(heights)) if whole.any() else 0.0,
            "frames": len(times)}, paddle


def speed(track: pose.PoseTrack, side: str | None) -> np.ndarray:
    left, right, _ = pose.wrist_speeds(track)
    return right if side == "right" else left if side == "left" else np.maximum(left, right)


def own_stroke(track: pose.PoseTrack, hit_at: float, side: str | None) -> int | None:
    """The frame of the followed player's swing peak at this hit, if it is their stroke:
    their bat wrist (or either, before the hand is known) peaks within 0.15 s of the sound,
    fast (STROKE_SPEED). The opponent's hit leaves the wrist moving into the ready position."""
    if not track.valid.any():
        return None
    v = speed(track, side)
    near = np.flatnonzero(np.abs(track.times - hit_at) <= 0.15)
    if not len(near):
        return None
    i = int(near[np.argmax(v[near])])
    return i if v[i] >= STROKE_SPEED else None


def strokes_only(hits: list[float]) -> list[float]:
    """One onset per stroke: drop onsets within SAME_STROKE of the previous kept one."""
    out: list[float] = []
    for h in sorted(hits):
        if not out or h - out[-1] > SAME_STROKE:
            out.append(h)
    return out


def probe_speeds(lms: list[np.ndarray], wid: int, hgt: int) -> dict:
    """Each wrist's speed over three frames PROBE apart, relative to the body centre, in torso
    lengths per second (0 for a wrist not seen well in all three)."""
    xy = [lm[:, :2] * [wid, hgt] for lm in lms]
    centre = [(p[11] + p[12] + p[23] + p[24]) / 4 for p in xy]
    torso = float(np.median([np.linalg.norm((p[11] + p[12]) / 2 - (p[23] + p[24]) / 2) for p in xy])) or 1.0
    out = {}
    for side, wi in (("left", pose.L_WRIST), ("right", pose.R_WRIST)):
        if min(lm[wi, 3] for lm in lms) < .5:
            out[side] = 0.0
            continue
        rel = [p[wi] - c for p, c in zip(xy, centre)]
        out[side] = round(float(max(np.linalg.norm(rel[1] - rel[0]), np.linalg.norm(rel[2] - rel[1])) / PROBE / torso), 2)
    return out


def probe_rally(follower: pose.Follower, video: str, rally: dict, out: HitPose, need: int = ENOUGH) -> list[dict]:
    """One decode of the rally; pose on the frames PROBE before, at and after each stroke onset
    and at LOW_FPS in between (identity). Returns per onset how fast each wrist moves there.
    Stops once `need` fast strokes are in (a 23 s montage rally was probed to its end for nothing)."""
    hits = strokes_only(rally["hit_times"])
    if not hits:
        return []
    start, end = max(0.0, hits[0] - 2 * PROBE), hits[-1] + 2 * PROBE
    every = max(1, round(FPS / LOW_FPS))
    want = {round((h + d - start) * FPS): (i, j) for i, h in enumerate(hits) for j, d in enumerate((-PROBE, 0.0, PROBE))}
    got: dict[tuple, np.ndarray] = {}
    probes: list[dict] = []
    first = True
    for k, (t, frame) in enumerate(frames(video, start, end, FPS)):
        if k not in want and k % every:
            continue
        arr, _ = follower.step(frame, cut=first)
        first = False
        out.frames += 1
        if k not in want:
            continue
        i, j = want[k]
        got[(i, j)] = arr
        if j < 2:
            continue
        lms = [got.get((i, jj)) for jj in range(3)]
        if any(lm is None or np.isnan(lm[[11, 12, 23, 24], 0]).any() for lm in lms):
            probes.append({"hit": hits[i], "left": 0.0, "right": 0.0, "seen": False})
        else:
            probes.append({"hit": hits[i], **probe_speeds(lms, frame.shape[1], frame.shape[0]), "seen": True})
        if sum(max(p["left"], p["right"]) >= STROKE_SPEED for p in probes) >= need:
            break
    return probes


def window_at(follower: pose.Follower, video: str, hit: float, side: str | None) -> HitWindow | None:
    """Full-rate pose from HALF before to HALF after one onset."""
    start = max(0.0, hit - HALF)
    times, lms, worlds, shots = _follow(follower, video, start, hit + HALF, FPS, cut=True)
    if len(times) < 5:
        return None
    tr = pose.make_track([t - start for t in times], lms, worlds, FPS, shots[0].shape[1], shots[0].shape[0],
                         {"source_fps": FPS, "stride": 1})
    win = HitWindow(hit=hit, track=tr, start=start)
    win.peak = own_stroke(tr, hit - start, side)
    win.own = win.peak is not None
    return win


def hit_pose(video: str, rallies: list[dict], identity: np.ndarray | None, side: str | None = None) -> HitPose:
    """Scan the busiest rallies, probe every stroke in the best ones, then full-rate pose
    around the fastest strokes (see module doc). rallies: {start, end, hits, hit_times}."""
    import mediapipe as mp
    from mediapipe.tasks.python import vision

    from .people import grab_frame

    out = HitPose()
    ranked = sorted(rallies, key=lambda r: (r["hits"], r["end"] - r["start"]), reverse=True)[:CANDIDATES]
    if not ranked:
        return out
    first = grab_frame(video, ranked[0]["start"])
    if first is None:
        return out
    with vision.PoseLandmarker.create_from_options(pose._landmarker_options()) as lmk:
        follower = pose.Follower(lmk, mp, first.shape[1], first.shape[0], identity)
        with timing.stage(f"scan {len(ranked)} rallies at {SCAN_FPS:g} fps"):
            for r in ranked:
                info, paddle = scan(follower, video, r)
                out.scan.append({"rally": [round(r["start"], 2), round(r["end"], 2)], **info, "paddle": paddle})
                out.frames += info.get("frames", 0)
                for k in paddle:
                    out.paddle[k] += paddle[k]
        usable = [k for k, s in enumerate(out.scan) if s["visible"] >= pose.MIN_VISIBLE]
        order = sorted(usable or range(len(ranked)), key=lambda k: -out.scan[k]["visible"] * out.scan[k]["height"])
        with timing.stage("probe the strokes (3 frames each)"):
            for k in order[:RALLIES]:
                found = sum(max(p["left"], p["right"]) >= STROKE_SPEED for p in out.probes)
                if found >= ENOUGH:
                    break
                out.rallies.append(ranked[k])
                out.probes += probe_rally(follower, video, ranked[k], out, need=ENOUGH - found)
        # The fastest wrist at an onset is the bat wrist when it is the player's own stroke.
        fast = sorted((p for p in out.probes if p["seen"]),
                      key=lambda p: -(p[side] if side else max(p["left"], p["right"])))
        with timing.stage("pose at the best strokes (30 fps)"):
            for p in fast[:ENOUGH]:
                w = window_at(follower, video, p["hit"], side)
                if w is not None:
                    out.windows.append(w)
                    out.frames += len(w.track.times)
    out.windows.sort(key=lambda w: w.hit)
    return out


def view(track: pose.PoseTrack) -> dict:
    """How well a window shows the player: share of frames head to ankles, share with the
    whole body inside the frame (not cut by its edge), and median body height (frame share)."""
    whole = pose.whole_body(track)
    lm = track.lm[track.valid]
    inside = float(((np.nanmin(lm[:, :, 0], axis=1) > .01) & (np.nanmax(lm[:, :, 0], axis=1) < .99)).mean()) if len(lm) else 0.0
    height = float(np.median(track.lm[whole, :, 1].max(1) - track.lm[whole, :, 1].min(1))) if whole.any() else 0.0
    return {"whole": float(whole.mean()), "inside": inside, "height": height}


def coached(hp: HitPose, side: str, wing: str | None = None) -> HitWindow | None:
    """The stroke to coach: one of the player's own, seen whole, inside the frame and big
    (a far or cut-off body's landmark jitter inflates its speed, and it makes a poor video),
    then fast, in a playing stance, of the requested wing when it can be told. On the montage
    the fastest swing was a far figure 0.21 of the frame high, or a near one cut by the edge."""
    from .pipeline import ready_stance
    from .strokes import STROKE_TYPES, detect

    own = [w for w in hp.windows if w.own]
    looks = {id(w): view(w.track) for w in own}
    clear = [w for w in own if looks[id(w)]["whole"] >= .8 and looks[id(w)]["inside"] >= .8]
    best, score = None, -1.0
    for w in clear or own:
        v = looks[id(w)]
        fast = min(float(speed(w.track, side)[w.peak]), 10.0)
        s = fast * v["whole"] * v["inside"] * v["height"] * (1.2 if ready_stance(w.track, w.peak) else 1.0)
        if wing:
            try:
                st, _ = detect(w.track, side, w.peak, wing=None)
                if STROKE_TYPES[st].stroke == wing:
                    s *= 1.5
            except Exception:
                pass
        if s > score:
            best, score = w, s
    return best


def body_track(hp: HitPose) -> pose.PoseTrack | None:
    """Every frame of the player across the full-rate windows, for body proportions."""
    tracks = [w.track for w in hp.windows if w.track.valid.any()]
    if not tracks:
        return None
    t0 = tracks[0]
    return pose.PoseTrack(fps=FPS, width=t0.width, height=t0.height,
                          times=np.concatenate([t.times + 100 * k for k, t in enumerate(tracks)]),
                          lm=np.concatenate([t.lm for t in tracks]), world=np.concatenate([t.world for t in tracks]),
                          meta={"stride": 1})
