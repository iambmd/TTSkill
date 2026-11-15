"""Drops rally candidates that are really a player bouncing the ball on the floor before serving.

The floor bounces sound like ball contacts and their spectrum overlaps real hits (checked on
IMG_8782.MOV), so audio alone can't tell them apart. The pose can: to bounce the ball on the
floor the player bends over with the hand below the hip, which never lasts long in a rally.
"""
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
SAMPLE_FPS = 5
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


def drop_floor_bounces(video: Path, rallies: list[Rally]) -> tuple[list[Rally], list[Rally]]:
    """Returns (kept, dropped). If pose can't run (e.g. missing libGLES), keeps everything."""
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        from technique.pose import model_path
    except Exception as exc:  # pose is an extra check; the cut still works without it
        print(f"floor-bounce check skipped: {exc}")
        return rallies, []

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
                frames.append([np.array([[p.x, p.y] for p in person]) for person in people])
            (dropped if crouch_fraction(frames) >= MAX_CROUCH else kept).append(r)
    return kept, dropped


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
