"""Clip joins in edited videos. A highlights montage is trimmed clips joined by crossfades,
often from one fixed camera, so the background never changes and a scene-cut detector sees
nothing. This finds the crossfades and regroups rally candidates around them: a rally never
spans a join, and the pieces of one clip stay together."""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks

from .rally import Rally

FPS = 10            # the pose filter's sample rate; scores are computed on those frames
HALF = 3            # the ramp is tested over 2*HALF frames (0.6 s; editors default to ~0.5 s)
TOL = 0.08          # a pixel "changed" when it moves this much of full range across the ramp
MIN_CHANGED = 0.004  # share of pixels that must change; fewer is noise
# Share of changed pixels that ramp linearly. Continuous recordings stay under .16 (p99)
# on the eval clips; the montage's joins score .36-.93.
JOIN_SCORE = 0.35
MERGE_GAP = 4.0     # pieces of one clip closer than this are one rally (the editor trimmed it)
SAME_JOIN = 0.8     # two detections closer than this are the same crossfade


def gray(rgb: np.ndarray) -> np.ndarray:
    """(n, H, W, 3) uint8 -> (n, H/4, W/4) float in 0..1, area-averaged so noise doesn't count."""
    n, h, w, _ = rgb.shape
    h4, w4 = h // 4, w // 4
    return rgb[:, :h4 * 4, :w4 * 4].reshape(n, h4, 4, w4, 4, 3).mean(axis=(2, 4, 5), dtype=np.float32) / 255


def dissolve_score(f: np.ndarray) -> np.ndarray:
    """Per frame: of the pixels that differ between HALF frames before and HALF after, the
    share whose every sample in between sits on the straight line from one to the other.
    A crossfade ramps all of them together; a moving player flips pixels in a frame or two."""
    out = np.zeros(len(f), np.float32)
    for i in range(HALF, len(f) - HALF):
        a, d = f[i - HALF], f[i + HALF] - f[i - HALF]
        changed = np.abs(d) > TOL
        if changed.mean() < MIN_CHANGED:
            continue
        linear = changed.copy()
        for k in range(1, 2 * HALF):
            linear &= np.abs(f[i - HALF + k] - (a + d * k / (2 * HALF))) < 0.22 * np.abs(d)
        out[i] = linear.sum() / changed.sum()
    return out


def find_joins(f: np.ndarray, t0: float = 0.0) -> list[float]:
    """Crossfade times (s) in gray frames `f` sampled at FPS from `t0`."""
    if len(f) <= 2 * HALF:
        return []
    peaks, _ = find_peaks(dissolve_score(f), height=JOIN_SCORE, distance=int(SAME_JOIN * FPS))
    return [t0 + float(p) / FPS for p in peaks]


def merge_joins(joins: list[float]) -> list[float]:
    """One time per crossfade: overlapping windows report the same join twice."""
    out: list[list[float]] = []
    for j in sorted(joins):
        if out and j - out[-1][-1] < SAME_JOIN:
            out[-1].append(j)
        else:
            out.append([j])
    return [float(np.mean(g)) for g in out]


def regroup(rallies: list[Rally], joins: list[float], min_hits: int = 4,
            merge_gap: float = MERGE_GAP,
            non_play: list[tuple[float, float]] | None = None) -> list[Rally]:
    """Split candidates at joins, then merge the pieces of one clip. Without joins (a
    continuous recording) nothing changes: there a quiet gap is as likely dead time."""
    if not joins:
        return rallies
    joins = sorted(set(joins))
    pieces: list[Rally] = []
    for r in sorted(rallies, key=lambda r: r.start):
        inside = [j for j in joins if r.start < j <= r.end]
        if not inside or r.times is None:
            pieces.append(r)
            continue
        for a, b in zip([-np.inf] + inside, inside + [np.inf]):
            t = r.times[(r.times >= a) & (r.times < b)]
            if len(t):
                pieces.append(Rally(float(t[0]), float(t[-1]), len(t), t))
    merged: list[Rally] = []
    for p in pieces:
        last = merged[-1] if merged else None
        crosses_non_play = last and any(a < p.end and b > last.start for a, b in non_play or [])
        if (last and p.start - last.end <= merge_gap and not crosses_non_play
                and not any(last.end <= j <= p.start for j in joins)):
            times = None if last.times is None or p.times is None else np.concatenate([last.times, p.times])
            merged[-1] = Rally(last.start, max(last.end, p.end), last.hits + p.hits, times)
        else:
            merged.append(p)
    out = [m for m in merged if m.hits >= min_hits]
    for r in out:
        i = clip_index(r.start, joins)
        hi = joins[i] if i < len(joins) else np.inf
        if r.end <= hi:  # legacy candidates without onset times cannot be split safely
            r.clip_bounds = (joins[i - 1] if i else 0.0, hi)
    return out


def clip_index(t: float, joins: list[float]) -> int:
    """Which clip (0-based, counting joins before `t`) a time belongs to."""
    return int(np.searchsorted(np.asarray(joins), t, side="right"))
