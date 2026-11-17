"""Ball-contact detection from audio (same idea as prototype/rally_detect.py).

Used here only to find *where* the interesting play is, so the technique breakdown
focuses on a real rally instead of a player walking to pick up the ball."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np


def load_audio(path: str | Path, sr: int = 22050) -> tuple[np.ndarray, int]:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr),
         "-f", "s16le", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0, sr


def detect_hits(x: np.ndarray, sr: int, threshold: float = 3.0) -> np.ndarray:
    from app.rally import audio_onsets
    return audio_onsets(x, sr, threshold)


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
    from app.rally import audio_onsets, group_rallies_anchored
    times, ratios = audio_onsets(x, sr, min(threshold, 2.0), with_ratios=True)
    return [{**r.to_dict(), "hit_times": times[(times >= r.start) & (times <= r.end)].tolist()}
            for r in group_rallies_anchored(times, ratios, threshold)]
