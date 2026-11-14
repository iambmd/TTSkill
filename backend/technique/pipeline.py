"""End-to-end technique pipeline.

video -> pick window (audio rally detection, else pose motion) -> 720p proxy of the window
      -> MediaPipe pose -> key moments -> analyzer (Claude or offline) -> StrokeBreakdown
      -> text-to-video prompts (+ optional provider hook) -> pose-overlay breakdown video
text  -> analyzer -> StrokeBreakdown -> prompts -> card-only video
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from scipy.ndimage import uniform_filter1d

from . import audio, media, pose
from .analyze import OfflineAnalyzer, get_analyzer, normalize_stroke
from .render import render_breakdown, render_text_only
from .video_prompt import build_prompts, generate_video

Progress = Callable[[str], None]


def _log(progress: Optional[Progress], msg: str):
    (progress or (lambda m: print(f"[technique] {m}", flush=True)))(msg)


def choose_window(src: str, duration: float, window_s: float, workdir: Path,
                  progress: Optional[Progress] = None) -> dict:
    if duration <= max(window_s * 1.25, 20.0):
        # short clips (e.g. a Short of a pro drilling): analyse all of it; the renderer
        # only plays the part around the key moments
        return {"start": 0.0, "end": duration, "reason": "whole clip",
                "hit_times": [h for r in audio.find_rallies(src) for h in r["hit_times"]]}
    rallies = audio.find_rallies(src)
    if rallies:
        best = max(rallies, key=lambda r: (r["hits"], r["end"] - r["start"]))
        start = max(0.0, best["start"] - 0.6)
        end = min(duration, start + window_s, best["end"] + 0.8)
        _log(progress, f"longest rally {best['start']:.1f}-{best['end']:.1f}s ({best['hits']} hits)")
        return {"start": start, "end": end, "reason": "longest rally by ball-contact sound",
                "rally": {k: best[k] for k in ("start", "end", "hits")},
                "hit_times": best["hit_times"]}
    _log(progress, "no rallies heard; scanning pose motion at 5 fps")
    scan = media.make_proxy(src, workdir / "scan.mp4", height=480, fps=5)
    tr = pose.extract_pose(scan)
    s, e = pose.best_window(tr, window_s)
    return {"start": s, "end": e, "reason": "most bat-hand motion"}


def key_moments(track: pose.PoseTrack, side: str,
                hit_times: Optional[list[float]] = None) -> tuple[list[float], int]:
    """[preparation, contact, finish] times (s) and the contact frame index.

    Contact = a fast bat-hand swing peak on the *forward* (upward) swing, preferring
    peaks that line up with a ball-contact sound when hit times are known (so walking or
    the drop into the backswing is not picked). Preparation = the lowest bat-hand point
    just before it (end of backswing); finish = the highest point just after it."""
    pk = pose.swing_peaks(track, side)
    dur = float(track.times[-1]) if len(track.times) else 0.0
    if len(pk) == 0:
        mid = len(track.times) // 2
        return [max(0, dur * 0.3), dur * 0.5, min(dur, dur * 0.7)], mid
    l, r, _ = pose.wrist_speeds(track)
    v = r if side != "left" else l
    wi = pose.R_WRIST if side != "left" else pose.L_WRIST
    xy = pose._interp_nan(track.lm[:, :, :2]) * np.array([track.width, track.height])
    hip_y = (xy[:, pose.L_HIP, 1] + xy[:, pose.R_HIP, 1]) / 2
    wy = uniform_filter1d(xy[:, wi, 1] - hip_y, size=max(1, int(track.fps * 0.07)))  # +down
    vy = np.gradient(wy)
    # strongest swing that leaves room for the lead-in and the finish
    ok = ([i for i in pk if 1.0 <= track.times[i] <= dur - 0.8]
          or [i for i in pk if 0.45 <= track.times[i] <= dur - 0.5] or list(pk))
    hits = np.array(hit_times or [])

    def score(i: int) -> float:
        s_ = float(v[i]) * (1.0 if vy[i] < 0 else 0.3)  # upward = forward swing
        if len(hits):
            dt = float(np.min(np.abs(hits - track.times[i])))
            s_ *= 0.25 + np.exp(-(dt / 0.12) ** 2)
        return s_

    p = int(max(ok, key=score))
    win = max(2, int(0.6 * track.fps))
    a0 = max(0, p - win)
    prep = a0 + int(np.argmax(wy[a0:p + 1])) if p > a0 else p
    b1 = min(len(wy), p + win + 1)
    fin = p + int(np.argmin(wy[p:b1]))
    gap = max(1, int(0.12 * track.fps))
    prep = min(prep, p - gap) if p - gap >= 0 else 0
    fin = max(fin, min(len(wy) - 1, p + gap))
    T = track.times
    return [float(T[max(prep, 0)]), float(T[p]), float(T[fin])], p


def run_video(src: str, out_dir: str, stroke: str = "forehand", player: Optional[str] = None,
              analyzer: str = "auto", window: Optional[tuple[float, float]] = None,
              window_s: float = 8.0, t2v_provider: str = "none",
              progress: Optional[Progress] = None, hand: str = "auto") -> dict:
    """hand: auto | left | right (the player's bat hand, used when the paddle isn't visible)."""
    t0 = time.time()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stroke = normalize_stroke(stroke)
    info = media.probe(src)
    _log(progress, f"input {info['width']}x{info['height']} {info['duration']:.1f}s")

    if window:
        win = {"start": window[0], "end": window[1], "reason": "user"}
    else:
        win = choose_window(src, info["duration"], window_s, out, progress)
    _log(progress, f"window {win['start']:.1f}-{win['end']:.1f}s ({win['reason']})")

    clip = str(media.make_proxy(src, out / "clip.mp4", height=720, fps=30,
                                start=win["start"], end=win["end"]))
    _log(progress, "running MediaPipe pose")
    track = pose.extract_pose(clip)
    side, how = pose.bat_side(clip, track, hand)
    _log(progress, f"bat hand: {side} ({how})")
    hits = [h - win["start"] for h in win.get("hit_times", [])
            if win["start"] <= h <= win["end"]]
    keys, peak_i = key_moments(track, side, hits)
    summary = pose.summarize(track, side)
    contact = pose.pose_metrics(track, peak_i, side) if len(track.times) else {}
    (out / "pose_summary.json").write_text(json.dumps(summary, indent=2))

    dur = win["end"] - win["start"]
    frame_times = sorted(set([round(x, 2) for x in np.linspace(0.2, max(0.3, dur - 0.2), 6)] + keys))
    a = get_analyzer(analyzer)
    _log(progress, f"analysing with {a.name}")
    try:
        if isinstance(a, OfflineAnalyzer):
            b = a.from_video(clip, stroke, frame_times, summary, keys, player, contact_metrics=contact)
        else:
            b = a.from_video(clip, stroke, frame_times, summary, keys, player)
    except Exception as e:  # LLM failure must not kill the demo
        _log(progress, f"{a.name} failed ({e}); using offline analyzer")
        b = OfflineAnalyzer().from_video(clip, stroke, frame_times, summary, keys, player,
                                         contact_metrics=contact)
    b.handedness = side if (how != "faster wrist") else b.handedness
    # make sure every step has a usable time inside the clip
    for s, k in zip(b.steps, keys):
        if s.key_time_s is None or not (0 <= s.key_time_s <= dur):
            s.key_time_s = k
    (out / "breakdown.json").write_text(b.model_dump_json(indent=2))

    prompts = build_prompts(b)
    (out / "video_prompt.json").write_text(json.dumps(prompts, indent=2))
    generated = generate_video(prompts, str(out / "generated.mp4"), t2v_provider)

    _log(progress, "rendering pose-overlay breakdown video")
    overlay = render_breakdown(clip, track, b, str(out / "breakdown.mp4"), side)

    result = {
        "kind": "technique_breakdown",
        "input": str(src),
        "stroke": stroke,
        "window": {k: v for k, v in win.items() if k != "hit_times"},
        "analyzer": b.source,
        "bat_hand": {"side": side, "how": how},
        "key_times_s": keys,
        "outputs": {
            "breakdown_json": str(out / "breakdown.json"),
            "video_prompt_json": str(out / "video_prompt.json"),
            "pose_summary_json": str(out / "pose_summary.json"),
            "overlay_video": overlay,
            "generated_video": generated,
            "clip": clip,
        },
        "elapsed_s": round(time.time() - t0, 1),
    }
    (out / "result.json").write_text(json.dumps(result, indent=2))
    _log(progress, f"done in {result['elapsed_s']}s -> {overlay}")
    return result


def run_text(text: str, out_dir: str, stroke: str = "forehand", player: Optional[str] = None,
             analyzer: str = "auto", t2v_provider: str = "none",
             progress: Optional[Progress] = None) -> dict:
    t0 = time.time()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stroke = normalize_stroke(stroke)
    a = get_analyzer(analyzer)
    try:
        b = a.from_text(text, stroke, player)
    except Exception as e:
        _log(progress, f"{a.name} failed ({e}); using offline analyzer")
        b = OfflineAnalyzer().from_text(text, stroke, player)
    (out / "breakdown.json").write_text(b.model_dump_json(indent=2))
    prompts = build_prompts(b)
    (out / "video_prompt.json").write_text(json.dumps(prompts, indent=2))
    generated = generate_video(prompts, str(out / "generated.mp4"), t2v_provider)
    video = render_text_only(b, str(out / "breakdown.mp4"))
    result = {
        "kind": "technique_breakdown", "input": "text", "stroke": stroke, "analyzer": b.source,
        "outputs": {"breakdown_json": str(out / "breakdown.json"),
                    "video_prompt_json": str(out / "video_prompt.json"),
                    "overlay_video": video, "generated_video": generated},
        "elapsed_s": round(time.time() - t0, 1),
    }
    (out / "result.json").write_text(json.dumps(result, indent=2))
    return result
