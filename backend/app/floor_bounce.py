"""Drops rally candidates that are not two people playing: pre-serve floor/table
bounces (a player bent over, hand below the hip), ball retrieval and walking (nobody
swinging), and noise from neighbouring courts or music (nobody at the table at all).

The sounds of these overlap real hits (checked on the labeled eval videos), so audio
alone can't tell them apart; the pose can. Each candidate rally is sampled at a few
frames per second and must show a person who is actually swinging."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import clips
from .rally import Rally

# MediaPipe pose landmark indices
L_SHOULDER, R_SHOULDER = 11, 12
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_ANKLE, R_ANKLE = 27, 28

BENT_TORSO = 0.55    # shoulder-to-hip height / hip-to-ankle height; ~0.75 standing in a rally
MAX_CROUCH = 0.25    # share of sampled frames a rally may spend crouched
MIN_PRESENCE = 0.5   # share of sampled frames that must show a player-sized person
MIN_SWING = 0.10     # share of sampled steps with a fast wrist (someone is striking)
SWING_SPEED = 2.5    # wrist speed that counts as a swing, in torso-lengths per second
MIN_TORSO = 0.07    # normalized torso length; smaller people are neighbouring courts
OTHER_COURT = 0.8    # a rally whose biggest figure is under this share of the clip's usual size
JOIN_MARGIN = 0.7    # seconds decoded each side of a candidate to catch a crossfade at its edge
# A stroke lasts ~0.2 s: at 5 fps a wide phone shot of a player seen from behind showed
# 0.04-0.13 swing on real rallies (IMG_8782), the same as pre-serve. 10 fps separates them.
SAMPLE_FPS = 10
WIDTH, HEIGHT = 640, 360  # pose only needs a small frame; letterboxed to a fixed size for the raw pipe


def is_crouched(lm: np.ndarray) -> bool:
    """`lm` is (33, >=2) normalized landmarks, y pointing down. Bent over with a hand below the hip."""
    y = lm[:, 1]
    shoulder = (y[L_SHOULDER] + y[R_SHOULDER]) / 2
    hip = (y[L_HIP] + y[R_HIP]) / 2
    ankle = (y[L_ANKLE] + y[R_ANKLE]) / 2
    if ankle <= hip:
        return False
    return (hip - shoulder) / (ankle - hip) < BENT_TORSO and max(y[L_WRIST], y[R_WRIST]) > hip


def crouch_fraction(frames: list[list[np.ndarray]]) -> float:
    """Share of frames where anyone is crouched. Each frame is a list of per-person landmarks."""
    if not frames:
        return 0.0
    return sum(any(is_crouched(p) for p in people) for people in frames) / len(frames)


def presence_fraction(frames: list[list[np.ndarray]]) -> float:
    if not frames:
        return 0.0
    return sum(bool(people) for people in frames) / len(frames)


def _torso(lm: np.ndarray) -> float:
    sh = (lm[L_SHOULDER] + lm[R_SHOULDER]) / 2
    hp = (lm[L_HIP] + lm[R_HIP]) / 2
    return float(np.linalg.norm(sh - hp)) + 1e-6


def swing_fraction(frames: list[list[np.ndarray]], fps: float = SAMPLE_FPS,
                   times: np.ndarray | None = None) -> float:
    """Share of steps where some person's wrist moves at swing speed. People are matched
    between consecutive frames by hip centre, so two players don't blur together."""
    if len(frames) < 2:
        return 0.0
    active = 0
    for i, (a, b) in enumerate(zip(frames, frames[1:])):
        if times is not None and not 0.5 / fps <= times[i + 1] - times[i] <= 1.5 / fps:
            continue  # regrouped candidates can have an unsampled quiet gap between them
        step = False
        for p in b:
            if not a:
                continue
            centres = [((q[L_HIP] + q[R_HIP]) / 2) for q in a]
            me = (p[L_HIP] + p[R_HIP]) / 2
            q = a[int(np.argmin([np.linalg.norm(me - c) for c in centres]))]
            torso = _torso(p)
            prev = (q[L_HIP] + q[R_HIP]) / 2
            if np.linalg.norm(me - prev) > torso or not 0.5 < _torso(q) / torso < 2:
                continue  # likely a cut or a different person
            speed = max(np.linalg.norm((p[w] - me) - (q[w] - prev))
                        for w in (L_WRIST, R_WRIST)) / torso * fps
            if speed > SWING_SPEED:
                step = True
                break
        active += step
    return active / (len(frames) - 1)


def why_not_play(frames: list[list[np.ndarray]], times: np.ndarray | None = None) -> str:
    """Empty when the span shows play, else the reason it doesn't: tiny background people,
    sustained pre-serve crouching, or static bodies."""
    players = [[lm for lm in people if _torso(lm) >= MIN_TORSO] for people in frames]
    if presence_fraction(players) < MIN_PRESENCE:
        return "no player in view"
    if crouch_fraction(players) >= MAX_CROUCH:
        return "bouncing the ball before a serve"
    if swing_fraction(players, times=times) < MIN_SWING:
        return "nobody swinging"
    return ""


def shows_play(frames: list[list[np.ndarray]]) -> bool:
    return not why_not_play(frames)


def figure_size(frames: list[list[np.ndarray]]) -> float:
    """Median torso length of the biggest person per frame: the near player's size."""
    sizes = [max(_torso(lm) for lm in people) for people in frames if people]
    return float(np.median(sizes)) if sizes else 0.0


def other_court(sizes: list[float]) -> list[bool]:
    """Per rally of one clip: is its biggest figure too small to be this table's near player?
    Sound from a neighbouring court passes every other check when its players are in view."""
    if len(sizes) < 2:
        return [False] * len(sizes)
    usual = float(np.median(sizes))
    return [s < OTHER_COURT * usual for s in sizes]


@dataclass
class Refined:
    kept: list[Rally]
    dropped: list[Rally]   # each with .note saying why
    joins: list[float]     # crossfade times found in an edited video


def drop_non_play(video: Path, rallies: list[Rally], min_hits: int = 4) -> tuple[list[Rally], list[Rally]]:
    """Returns (kept, dropped). If pose can't run (e.g. missing libGLES), keeps everything."""
    r = refine(video, rallies, min_hits)
    return r.kept, r.dropped


def refine(video: Path, rallies: list[Rally], min_hits: int = 4) -> Refined:
    """Audio proposes, video decides: regroup candidates around clip joins, then keep the
    ones that show this table's players in play."""
    if not rallies:
        return Refined([], [], [])
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        from technique.pose import model_path
    except Exception as exc:  # pose is an extra check; the cut still works without it
        print(f"non-play pose check skipped: {exc}")
        return Refined(rallies, [], [])

    try:
        return _refine(video, rallies, min_hits, mp, BaseOptions, vision, model_path)
    except Exception as exc:
        print(f"non-play pose check skipped: {exc}")
        return Refined(rallies, [], [])


def _refine(video: Path, rallies: list[Rally], min_hits: int, mp, BaseOptions, vision, model_path) -> Refined:
    opts = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path())),
        running_mode=vision.RunningMode.IMAGE,
        num_poses=2,
        min_pose_detection_confidence=0.3,
    )
    rallies = sorted(rallies, key=lambda r: r.start)
    seen: list[tuple[float, list[np.ndarray]]] = []   # (time, people) for every posed frame
    joins: list[float] = []
    with vision.PoseLandmarker.create_from_options(opts) as landmarker:
        for r in rallies:
            # A margin each side, so a crossfade at the edge of a candidate is still seen.
            t0 = max(0.0, r.start - JOIN_MARGIN)
            rgb = _frames(video, t0, r.end + JOIN_MARGIN)
            joins += clips.find_joins(clips.gray(rgb), t0)
            for k, frame in enumerate(rgb):
                t = t0 + k / SAMPLE_FPS
                if r.start <= t <= r.end:
                    people = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)).pose_landmarks
                    seen.append((t, [np.array([[p.x, p.y] for p in person]) for person in people]))
    times = np.array([t for t, _ in seen])
    if joins:
        # An edited video: look for joins in every gap between candidates, not only short
        # ones. Clip membership drives the court check below, and a crossfade in a 4.0 s gap
        # (129.2 s on the montage) put a rally into the previous gym's clip, where the near
        # player is bigger, so it was dropped as "another court".
        for a, b in gaps_to_scan(rallies):
            joins += scan_joins(video, a, b)
        joins = clips.merge_joins(joins)
        # Do this before merging: a retrieval/pre-serve candidate otherwise joins two
        # rallies through a chain of short gaps, and its non-play gets averaged away.
        non_play = []
        for r in rallies:
            indices = np.flatnonzero((times >= r.start) & (times <= r.end))
            if why_not_play([seen[i][1] for i in indices], times[indices]):
                non_play.append((r.start, r.end))
        rallies = clips.regroup(rallies, joins, min_hits, non_play=non_play)

    kept: list[Rally] = []
    dropped: list[Rally] = []
    sizes: list[float] = []
    for r in rallies:
        indices = np.flatnonzero((times >= r.start) & (times <= r.end))
        frames = [seen[i][1] for i in indices]
        r.note = why_not_play(frames, times[indices])
        if r.note:
            dropped.append(r)
        else:
            kept.append(r)
            sizes.append(figure_size(frames))
    # Within each clip, a rally whose figures are all small is another court.
    for c in {clips.clip_index(r.start, joins) for r in kept}:
        idx = [i for i, r in enumerate(kept) if clips.clip_index(r.start, joins) == c]
        for i, small in zip(idx, other_court([sizes[i] for i in idx])):
            if small:
                kept[i].note = "another court"
    dropped += [r for r in kept if r.note]
    kept = [r for r in kept if not r.note]
    return Refined(kept, sorted(dropped, key=lambda r: r.start), joins)


def gaps_to_scan(rallies: list[Rally]) -> list[tuple[float, float]]:
    """Gaps between consecutive candidates not already covered by their join margins."""
    return [(a.end, b.start) for a, b in zip(rallies, rallies[1:]) if b.start - a.end > 2 * JOIN_MARGIN]


def chunks(start: float, end: float, size: float = 20.0) -> list[tuple[float, float]]:
    """[start, end] in pieces of at most `size` s that overlap by one crossfade test window,
    so a join on a boundary is still seen; decoding a long gap at once would hold ~70 MB/10 s."""
    overlap = 2 * clips.HALF / SAMPLE_FPS
    out, t = [], start
    while t < end:
        stop = min(end, t + size)
        out.append((t, stop))
        if stop >= end:
            break
        t = stop - overlap
    return out


def scan_joins(video: Path, start: float, end: float) -> list[float]:
    joins: list[float] = []
    for a, b in chunks(start, end):
        joins += clips.find_joins(clips.gray(_frames(video, a, b)), a)
    return joins


def drop_floor_bounces(video: Path, rallies: list[Rally]) -> tuple[list[Rally], list[Rally]]:
    """Old name, kept for callers; the check now also drops no-player and no-swing spans."""
    return drop_non_play(video, rallies)


def _frames(video: Path, start: float, end: float) -> np.ndarray:
    """Small RGB frames from [start, end] at SAMPLE_FPS. ffmpeg seeking is much faster than
    OpenCV's on phone HEVC."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{end - start:.3f}",
         "-vf", f"fps={SAMPLE_FPS},scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
               f"pad={WIDTH}:{HEIGHT}:-1:-1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, HEIGHT, WIDTH, 3)
