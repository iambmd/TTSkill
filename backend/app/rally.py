"""Rally detection from the sound of ball contact.

Ported from prototype/rally_detect.py. Still to do (see build plan): shoe-squeak
rejection via spectral flatness and transient length.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.ndimage import median_filter
from scipy.signal import butter, find_peaks, sosfiltfilt

FRAME_S = 0.005  # 5 ms envelope frames


@dataclass
class Rally:
    start: float
    end: float
    hits: int

    @property
    def shots(self) -> int:
        # Each shot is roughly a paddle hit plus a table bounce.
        return max(1, round(self.hits / 2))

    def to_dict(self) -> dict:
        return {"start": round(self.start, 2), "end": round(self.end, 2), "hits": self.hits, "shots": self.shots}


def extract_audio(video: Path, wav: Path, sr: int = 22050) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sr), str(wav)],
        check=True,
    )
    return wav


def detect_hits(wav: Path, threshold: float = 3.0) -> np.ndarray:
    sr, x = wavfile.read(wav)
    x = x.astype(np.float32) / 32768
    if x.ndim > 1:
        x = x.mean(axis=1)
    sos = butter(4, [2000, 6000], btype="band", fs=sr, output="sos")
    y = sosfiltfilt(sos, x)
    hop = int(sr * FRAME_S)
    env = np.sqrt(np.convolve(y**2, np.ones(hop) / hop, "same"))[::hop]
    base = median_filter(env, size=int(1.0 / FRAME_S))
    onset = env / (base + 1e-6)
    peaks, _ = find_peaks(onset, height=threshold, distance=int(0.12 / FRAME_S))
    return peaks * FRAME_S


def group_rallies(hits: np.ndarray, gap: float = 1.6, min_hits: int = 4) -> list[Rally]:
    if len(hits) == 0:
        return []
    groups: list[list[float]] = [[float(hits[0])]]
    for t in hits[1:]:
        if t - groups[-1][-1] < gap:
            groups[-1].append(float(t))
        else:
            groups.append([float(t)])
    return [Rally(g[0], g[-1], len(g)) for g in groups if len(g) >= min_hits]


def detect_rallies(video: Path, workdir: Path, threshold: float = 3.0, gap: float = 1.6, min_hits: int = 4) -> list[Rally]:
    wav = extract_audio(video, workdir / "audio.wav")
    return group_rallies(detect_hits(wav, threshold), gap, min_hits)
