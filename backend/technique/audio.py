"""Ball-contact detection from audio (same idea as prototype/rally_detect.py).

Used here only to find *where* the interesting play is, so the technique breakdown
focuses on a real rally instead of a player walking to pick up the ball."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import butter, find_peaks, sosfiltfilt


def load_audio(path: str | Path, sr: int = 22050) -> tuple[np.ndarray, int]:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr),
         "-f", "s16le", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0, sr


def detect_hits(x: np.ndarray, sr: int, threshold: float = 3.0) -> np.ndarray:
    if len(x) < sr:
        return np.array([])
    sos = butter(4, [2000, min(6000, sr / 2 - 100)], btype="band", fs=sr, output="sos")
    y = sosfiltfilt(sos, x)
    hop = int(sr * 0.005)
    env = np.sqrt(np.convolve(y ** 2, np.ones(hop) / hop, "same"))[::hop]
    base = median_filter(env, size=200)
    onset = env / (base + 1e-6)
    pk, _ = find_peaks(onset, height=threshold, distance=int(0.12 / 0.005))
    return pk * 0.005


def group_rallies(hits: np.ndarray, gap: float = 1.6, min_hits: int = 4) -> list[dict]:
    if len(hits) == 0:
        return []
    groups, cur = [], [hits[0]]
    for t in hits[1:]:
        if t - cur[-1] < gap:
            cur.append(t)
        else:
            groups.append(cur)
            cur = [t]
    groups.append(cur)
    return [
        {"start": float(g[0]), "end": float(g[-1]), "hits": len(g), "hit_times": [float(h) for h in g]}
        for g in groups if len(g) >= min_hits
    ]


def find_rallies(path: str | Path, threshold: float = 3.0) -> list[dict]:
    try:
        x, sr = load_audio(path)
    except subprocess.CalledProcessError:
        return []  # no audio track
    return group_rallies(detect_hits(x, sr, threshold))
