"""Drops rally candidates that are not two people playing: pre-serve floor/table
bounces (a player bent over, hand below the hip), ball retrieval and walking (nobody
swinging), and noise from neighbouring courts or music (nobody at the table at all).

The sounds of these overlap real hits (checked on the labeled eval videos), so audio
alone can't tell them apart; the pose can. Each candidate rally is sampled at a few
frames per second and must show a person who is actually swinging."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

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


def swing_fraction(frames: list[list[np.ndarray]], fps: float = SAMPLE_FPS) -> float:
    """Share of steps where some person's wrist moves at swing speed. People are matched
    between consecutive frames by hip centre, so two players don't blur together."""
    if len(frames) < 2:
        return 0.0
    active = 0
    for a, b in zip(frames, frames[1:]):
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


def shows_play(frames: list[list[np.ndarray]]) -> bool:
    """Reject tiny background people, static bodies, and sustained pre-serve crouching."""
    players = [[lm for lm in people if _torso(lm) >= MIN_TORSO] for people in frames]
    return (presence_fraction(players) >= MIN_PRESENCE
            and swing_fraction(players) >= MIN_SWING
            and crouch_fraction(players) < MAX_CROUCH)


def drop_non_play(video: Path, rallies: list[Rally]) -> tuple[list[Rally], list[Rally]]:
    """Returns (kept, dropped). If pose can't run (e.g. missing libGLES), keeps everything."""
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        from technique.pose import model_path
    except Exception as exc:  # pose is an extra check; the cut still works without it
        print(f"non-play pose check skipped: {exc}")
        return rallies, []

    try:
        return _filter(video, rallies, mp, BaseOptions, vision, model_path)
    except Exception as exc:
        print(f"non-play pose check skipped: {exc}")
        return rallies, []


def _filter(video: Path, rallies: list[Rally], mp, BaseOptions, vision, model_path) -> tuple[list[Rally], list[Rally]]:
    opts = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path())),
        running_mode=vision.RunningMode.IMAGE,
        num_poses=2,
        min_pose_detection_confidence=0.3,
    )
    kept: list[Rally] = []
    dropped: list[Rally] = []
    with vision.PoseLandmarker.create_from_options(opts) as landmarker:
        for r in rallies:
            frames: list[list[np.ndarray]] = []
            for rgb in _frames(video, r.start, r.end):
                people = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)).pose_landmarks
                lms = [np.array([[p.x, p.y] for p in person]) for person in people]
                frames.append(lms)
            ok = shows_play(frames)
            (kept if ok else dropped).append(r)
    return kept, dropped


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
