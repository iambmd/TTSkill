"""Rally detection from the sound of ball contact.

Strong audio onsets delimit candidate rallies; weaker onsets count only inside those
bounds. Audio alone cannot distinguish paddle/table/floor contacts. The optional
pose filter rejects obvious non-play. The local onset model remains experimental.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
from scipy.io import wavfile
from scipy.ndimage import median_filter
from scipy.signal import butter, find_peaks, sosfiltfilt

FRAME_S = 0.005  # 5 ms envelope frames
MODEL_PATH = Path(__file__).parent / "onset_model.json"
FEATURE_NAMES = ["peak_ratio", "sharpness", "decay_ms", "dur_half_ms",
                 "centroid_khz", "flatness", "mid_over_low", "high_over_mid",
                 "peak_db", "bg_db"]


@dataclass
class Rally:
    start: float
    end: float
    hits: int
    # Onset times, so a candidate can be split at a clip join (app/clips.py).
    times: np.ndarray | None = field(default=None, repr=False, compare=False)
    note: str = field(default="", compare=False)  # why the non-play check dropped it
    clip_bounds: tuple[float, float] | None = field(default=None, compare=False)

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


def detect_hits(wav: Path, threshold: float = 3.0, with_ratios: bool = False) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
    sr, x = wavfile.read(wav)
    x = x.astype(np.float32) / 32768
    if x.ndim > 1:
        x = x.mean(axis=1)
    return audio_onsets(x, sr, threshold, with_ratios)


def audio_onsets(x: np.ndarray, sr: int, threshold: float = 3.0,
                 with_ratios: bool = False) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
    """Shared onset extractor for Auto-Cut and technique window/contact selection."""
    if len(x) < sr:
        empty = np.array([], dtype=float)
        return (empty, empty) if with_ratios else empty
    sos = butter(4, [2000, 6000], btype="band", fs=sr, output="sos")
    y = sosfiltfilt(sos, x)
    hop = int(sr * FRAME_S)
    env = np.sqrt(np.convolve(y**2, np.ones(hop) / hop, "same"))[::hop]
    base = median_filter(env, size=int(1.0 / FRAME_S))
    onset = env / (base + 1e-6)
    peaks, props = find_peaks(onset, height=threshold, distance=int(0.12 / FRAME_S))
    if with_ratios:
        return peaks * hop / sr, props["peak_heights"]
    return peaks * hop / sr


def onset_features(x: np.ndarray, sr: int, t: float) -> np.ndarray:
    """Features of the sound at onset time `t` (seconds), from a short local window.
    A paddle pop is loud, sharp, short and mid-band; floor bounces and squeaks are
    duller, longer or low; music and far-court noise barely rise over the background."""
    a = max(0, int((t - 0.15) * sr))
    seg = x[a:int((t + 0.35) * sr)].astype(np.float32)
    if len(seg) < int(0.2 * sr):
        seg = np.pad(seg, (0, int(0.2 * sr) - len(seg)))
    sos = butter(4, [1000, min(9000, sr / 2 - 100)], btype="band", fs=sr, output="sos")
    y = sosfiltfilt(sos, seg)
    hop = max(1, int(sr * 0.001))  # 1 ms envelope
    env = np.sqrt(np.convolve(y ** 2, np.ones(hop) / hop, "same"))[::hop]
    t0 = int((t * sr - a) / hop)  # onset position in env frames
    search = env[max(0, t0 - 30):t0 + 80]
    pk_i = int(np.argmax(search)) + max(0, t0 - 30)
    peak = env[pk_i] + 1e-9
    bg = np.median(env[max(0, t0 - 150):max(1, t0 - 50)]) + 1e-9
    pre = env[max(0, pk_i - 10)] + 1e-9
    after = env[pk_i:pk_i + 300]
    below = np.nonzero(after < 0.25 * peak)[0]
    decay_ms = float(below[0]) if len(below) else 300.0
    dur_half_ms = float((after >= 0.5 * peak).sum())
    # spectrum of ~46 ms around the peak
    c = a + pk_i * hop
    w = x[max(0, c - 512):c + 512].astype(np.float32)
    if len(w) < 1024:
        w = np.pad(w, (0, 1024 - len(w)))
    mag = np.abs(np.fft.rfft(w * np.hanning(len(w)))) + 1e-9
    freqs = np.fft.rfftfreq(len(w), 1 / sr)
    centroid = float((freqs * mag).sum() / mag.sum()) / 1000.0
    flatness = float(np.exp(np.mean(np.log(mag))) / mag.mean())
    def band(lo, hi):
        return float((mag[(freqs >= lo) & (freqs < hi)] ** 2).sum()) + 1e-9
    mid_over_low = np.log10(band(2000, 6000) / band(300, 1500))
    high_over_mid = np.log10(band(6000, 10000) / band(2000, 6000))
    return np.array([min(peak / bg, 100.0), min(peak / pre, 100.0), decay_ms, dur_half_ms,
                     centroid, flatness, mid_over_low, high_over_mid,
                     20 * np.log10(peak), 20 * np.log10(bg)], np.float32)


def load_model(path: Path = MODEL_PATH) -> dict | None:
    if not path.exists():
        return None
    m = json.loads(path.read_text())
    return {k: np.array(m[k], np.float32) for k in ("w", "mean", "std")} | {"b": m["b"]}


def play_scores(x: np.ndarray, sr: int, onsets: np.ndarray, model: dict | None = None) -> np.ndarray:
    """P(play sound) for each onset; all 1.0 when no model file is present."""
    model = model or load_model()
    if model is None or len(onsets) == 0:
        return np.ones(len(onsets), np.float32)
    feats = np.stack([onset_features(x, sr, t) for t in onsets])
    z = (feats - model["mean"]) / model["std"]
    return 1 / (1 + np.exp(-(z @ model["w"] + model["b"])))


def group_rallies(hits: np.ndarray, gap: float = 1.6, min_hits: int = 4) -> list[Rally]:
    if len(hits) == 0:
        return []
    groups: list[list[float]] = [[float(hits[0])]]
    for t in hits[1:]:
        if t - groups[-1][-1] < gap:
            groups[-1].append(float(t))
        else:
            groups.append([float(t)])
    return [Rally(g[0], g[-1], len(g), np.array(g)) for g in groups if len(g) >= min_hits]


def group_rallies_anchored(times: np.ndarray, ratios: np.ndarray,
                           threshold: float = 3.0, gap: float = 1.6,
                           min_hits: int = 4) -> list[Rally]:
    """Strong onsets establish boundaries; soft sounds inside them contribute counts.

    A weak chain cannot override the user's gap. Bounded edge sounds may include
    prep/bounces; exact contact types require labels we do not yet have.
    Counts remain audio events, not a claim of classified paddle contacts.
    """
    anchors = times[ratios >= threshold]
    groups = group_rallies(anchors, gap, min_hits=2)
    rallies = []
    for i, g in enumerate(groups):
        # Include a bounded lead-in/trailing bounce, never chain across a break.
        left = max(g.start - 0.5, (groups[i - 1].end + g.start) / 2 if i else -np.inf)
        right = min(g.end + 1.2, (g.end + groups[i + 1].start) / 2 if i + 1 < len(groups) else np.inf)
        members = times[(times >= left) & (times < right)]
        if len(members) >= min_hits:
            rallies.append(Rally(float(members[0]), float(members[-1]), len(members), members))
    return rallies


def detect_rallies(video: Path, workdir: Path, threshold: float = 3.0, gap: float = 1.6, min_hits: int = 4,
                   audio_ready: Callable[[], None] | None = None) -> list[Rally]:
    wav = extract_audio(video, workdir / "audio.wav")
    if audio_ready:
        audio_ready()
    times, ratios = detect_hits(wav, min(threshold, 2.0), with_ratios=True)
    return group_rallies_anchored(times, ratios, threshold, gap, min_hits)
