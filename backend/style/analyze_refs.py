"""Measure the editing style of the reference videos in data/style_ref/ (git-ignored).

For each video: scene cuts (pacing), freeze frames (ffmpeg freezedetect), slow-motion
stretches (runs of duplicated frames / very low motion that are not frozen) and where
text sits on screen. Writes data/style_ref/analysis/metrics.json plus one contact sheet per
video (a frame from every scene) for reading the card layout by eye.
Usage: cd backend && .venv/bin/python -m style.analyze_refs"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

REF = Path(__file__).resolve().parents[1] / "data" / "style_ref"
OUT = REF / "analysis"


def _ffmpeg_log(video: Path, vf: str) -> str:
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-vf", vf,
                           "-an", "-f", "null", "-"], capture_output=True, text=True).stderr


def scene_cuts(video: Path, thr: float = 0.3) -> list[float]:
    log = _ffmpeg_log(video, f"select='gt(scene,{thr})',showinfo")
    return [float(m) for m in re.findall(r"pts_time:([\d.]+)", log)]


def freezes(video: Path) -> list[tuple[float, float]]:
    log = _ffmpeg_log(video, "freezedetect=n=0.002:d=0.35")
    starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", log)]
    durs = [float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", log)]
    return list(zip(starts, durs))


def motion(video: Path) -> tuple[np.ndarray, float]:
    """Mean absolute difference between consecutive frames (64px wide grey), per frame."""
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    prev, diffs = None, []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(cv2.resize(f, (64, int(64 * f.shape[0] / f.shape[1]))), cv2.COLOR_BGR2GRAY)
        g = g.astype(np.float32)
        if prev is not None:
            diffs.append(float(np.abs(g - prev).mean()))
        prev = g
    cap.release()
    return np.array(diffs), fps


def slowmo_spans(d: np.ndarray, fps: float, frozen: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Seconds where many frames repeat (duplicated-frame slow motion) or motion drops far
    below the video's typical level, excluding freeze frames."""
    if len(d) < fps:
        return []
    dup = d < 0.15
    win = int(fps)
    dup_ratio = np.convolve(dup.astype(float), np.ones(win) / win, "same")
    level = np.convolve(d, np.ones(win) / win, "same")
    typical = np.median(level[level > 0.3]) if (level > 0.3).any() else 1.0
    slow = ((dup_ratio > 0.3) & (dup_ratio < 0.85)) | ((level < 0.35 * typical) & (level > 0.15))
    t = np.arange(len(d)) / fps
    for s, du in frozen:
        slow[(t >= s) & (t <= s + du)] = False
    spans, start = [], None
    for i, v in enumerate(slow):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= int(0.6 * fps):
                spans.append((round(start / fps, 2), round(i / fps, 2)))
            start = None
    return spans


def text_bands(frame: np.ndarray) -> dict:
    """Share of text-like pixels (bright/dark edges in thin horizontal runs) per third."""
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    grad = cv2.morphologyEx(g, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    _, bw = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1)))
    n, _, stats, _ = cv2.connectedComponentsWithStats(bw)
    h, w = g.shape
    bands = np.zeros(3)
    for x, y, cw, ch, area in stats[1:]:
        if 8 < ch < h * 0.08 and cw > ch * 2.5 and cw < w * 0.95 and area > 0.3 * cw * ch:
            bands[min(2, int((y + ch / 2) / h * 3))] += cw * ch
    total = bands.sum() or 1.0
    return {"top": round(bands[0] / total, 2), "middle": round(bands[1] / total, 2),
            "bottom": round(bands[2] / total, 2), "text_area": round(float(bands.sum() / (h * w)), 3)}


def contact_sheet(video: Path, times: list[float], path: Path, cols: int = 6) -> list[dict]:
    cap = cv2.VideoCapture(str(video))
    tiles, layout = [], []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        if not ok:
            continue
        layout.append({"t": round(t, 2), **text_bands(f)})
        tw = 240
        tile = cv2.resize(f, (tw, int(tw * f.shape[0] / f.shape[1])))
        cv2.putText(tile, f"{t:.1f}s", (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        tiles.append(tile)
    cap.release()
    if tiles:
        th = max(t.shape[0] for t in tiles)
        tiles = [cv2.copyMakeBorder(t, 0, th - t.shape[0], 0, 0, cv2.BORDER_CONSTANT) for t in tiles]
        while len(tiles) % cols:
            tiles.append(np.zeros_like(tiles[0]))
        rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
        cv2.imwrite(str(path), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
    return layout


def motion_cuts(d: np.ndarray, fps: float) -> list[float]:
    """Hard cuts as isolated spikes in frame difference (works when footage sits inside a
    fixed card layout, where ffmpeg's whole-frame scene score stays low)."""
    if len(d) < 3:
        return []
    base = np.median(d[d > 0.05]) if (d > 0.05).any() else 1.0
    idx = [i for i in range(1, len(d) - 1) if d[i] > max(4 * base, 3.0) and d[i] > 2 * max(d[i - 1], d[i + 1])]
    out: list[float] = []
    for i in idx:
        t = (i + 1) / fps
        if not out or t - out[-1] > 0.3:
            out.append(round(t, 2))
    return out


def analyse(video: Path, meta: dict) -> dict:
    d, fps = motion(video)
    cuts = sorted(set(scene_cuts(video, 0.12)) | set(motion_cuts(d, fps)))
    dur = len(d) / fps if len(d) else 0.0
    fr = freezes(video)
    slow = slowmo_spans(d, fps, fr)
    bounds = [0.0] + cuts + [dur]
    scenes = [round(b - a, 2) for a, b in zip(bounds, bounds[1:]) if b - a > 0.05]
    step = 1.0 if dur < 30 else 6.0   # fixed grid: shorts every second, long videos every 6 s
    mids = list(np.arange(0.5, max(dur - 0.2, 0.6), step))[:36]
    layout = contact_sheet(video, mids, OUT / f"{video.stem}.jpg")
    return {
        **meta, "duration_s": round(dur, 1), "fps": round(fps, 2),
        "scenes": len(scenes), "median_scene_s": round(float(np.median(scenes)), 2) if scenes else None,
        "scene_lengths_s": scenes,
        "freezes": [{"t": round(s, 2), "dur": round(du, 2)} for s, du in fr],
        "slowmo": [{"start": a, "end": b} for a, b in slow],
        "text_layout": layout,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = json.loads((REF / "index.json").read_text())
    results = []
    for e in index:
        v = REF / f"{e['id']}.mp4"
        if v.exists():
            print("analysing", e["id"], e["title"])
            results.append(analyse(v, e))
    (OUT / "metrics.json").write_text(json.dumps(results, indent=2))
    print(f"wrote {OUT / 'metrics.json'}")


if __name__ == "__main__":
    main()
