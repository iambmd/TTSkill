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

from . import audio, media, pose, strokes
from .analyze import OfflineAnalyzer, get_analyzer, normalize_stroke
from .render import render_breakdown, render_text_only
from .video_prompt import build_prompts, generate_video

Progress = Callable[[str], None]


def _log(progress: Optional[Progress], msg: str):
    (progress or (lambda m: print(f"[technique] {m}", flush=True)))(msg)


CANDIDATE_RALLIES = 6   # busiest rallies checked for how well the player is seen


def player_view(src: str, start: float, end: float, identity: np.ndarray, path: Path) -> tuple[float, float]:
    """(share of frames showing the identified player head to ankles, their median height as a
    fraction of the frame) over [start, end], from a 4 fps scan. A close camera that cuts the
    player at the waist gives guessed knee and stance numbers; a far player gives coarse ones."""
    scan = media.make_proxy(src, path, height=480, fps=4, start=start, end=end)
    track = pose.extract_pose(scan, identity=identity)
    if not len(track.times):
        return 0.0, 0.0
    whole = pose.whole_body(track)
    heights = track.lm[whole, :, 1].max(axis=1) - track.lm[whole, :, 1].min(axis=1)
    return float(whole.mean()), float(np.median(heights)) if whole.any() else 0.0


def choose_window(src: str, duration: float, window_s: float, workdir: Path,
                  progress: Optional[Progress] = None, identity: Optional[np.ndarray] = None) -> dict:
    """identity: the coached player's torso template. When given, the window is the busiest
    rally in which that player is actually visible, not one where they are the far player."""
    if duration <= max(window_s * 1.25, 20.0):
        # short clips (e.g. a Short of a pro drilling): analyse all of it; the renderer
        # only plays the part around the key moments
        return {"start": 0.0, "end": duration, "reason": "whole clip",
                "hit_times": [h for r in audio.find_rallies(src) for h in r["hit_times"]]}
    rallies = audio.find_rallies(src)
    if rallies:
        ranked = sorted(rallies, key=lambda r: (r["hits"], r["end"] - r["start"]), reverse=True)

        def span(r: dict) -> tuple[float, float]:
            start = max(0.0, r["start"] - 0.6)
            return start, min(duration, start + window_s, r["end"] + 0.8)

        best, reason, seen = ranked[0], "longest rally by ball-contact sound", None
        if identity is not None and len(ranked) > 1:
            views = [player_view(src, *span(r), identity, Path(workdir) / f"scan_{i}.mp4")
                     for i, r in enumerate(ranked[:CANDIDATE_RALLIES])]
            # How much of you there is to measure: seen whole often, and big in the frame.
            # Below the pose floor (require_player) a rally can't be analysed at all.
            usable = [k for k, (share, _) in enumerate(views) if share >= pose.MIN_VISIBLE]
            i = max(usable, key=lambda k: views[k][0] * views[k][1]) if usable else 0
            best, seen = ranked[i], round(views[i][0], 2)
            reason = "busy rally where you're seen best" if i else reason
            _log(progress, f"player (visible, height) in candidate rallies: "
                           f"{[(round(a, 2), round(b, 2)) for a, b in views]}")
        start, end = span(best)
        _log(progress, f"rally {best['start']:.1f}-{best['end']:.1f}s ({best['hits']} hits)")
        return {"start": start, "end": end, "reason": reason, "visible": seen,
                "rally": {k: best[k] for k in ("start", "end", "hits")},
                "hit_times": best["hit_times"]}
    _log(progress, "no rallies heard; scanning pose motion at 5 fps")
    scan = media.make_proxy(src, workdir / "scan.mp4", height=480, fps=5)
    tr = pose.extract_pose(scan)
    s, e = pose.best_window(tr, window_s)
    return {"start": s, "end": e, "reason": "most bat-hand motion"}


def key_moments(track: pose.PoseTrack, side: str, hit_times: Optional[list[float]] = None,
                direction: str = "up", window_s: float = 0.6) -> tuple[list[float], int]:
    """[preparation, contact, finish] times (s) and the contact frame index.

    Contact = a fast bat-hand swing peak moving in the stroke's `direction` (up for topspin
    strokes, down for pushes and chops, any for serves), preferring peaks that line up with
    a ball-contact sound when hit times are known (so walking or the drop into the backswing
    is not picked). Preparation/finish = the bat hand's turning points within `window_s`
    before/after contact (lowest then highest for upward strokes, the reverse for downward)."""
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
        along = direction == "any" or (vy[i] < 0) == (direction == "up")
        s_ = float(v[i]) * (1.0 if along else 0.3)
        if len(hits):
            dt = float(np.min(np.abs(hits - track.times[i])))
            s_ *= 0.25 + np.exp(-(dt / 0.12) ** 2)
        return s_

    p = int(max(ok, key=score))
    win = max(2, int(window_s * track.fps))
    a0 = max(0, p - win)
    b1 = min(len(wy), p + win + 1)
    if direction == "down":   # highest point before, lowest after
        prep = a0 + int(np.argmin(wy[a0:p + 1])) if p > a0 else p
        fin = p + int(np.argmax(wy[p:b1]))
    elif direction == "up":   # lowest point before (end of backswing), highest after
        prep = a0 + int(np.argmax(wy[a0:p + 1])) if p > a0 else p
        fin = p + int(np.argmin(wy[p:b1]))
    else:
        prep, fin = a0 + (p - a0) // 2, min(len(wy) - 1, p + win // 2)
    gap = max(1, int(0.12 * track.fps))
    prep = min(prep, p - gap) if p - gap >= 0 else 0
    fin = max(fin, min(len(wy) - 1, p + gap))
    T = track.times
    return [float(T[max(prep, 0)]), float(T[p]), float(T[fin])], p


def _stroke_plan(track: pose.PoseTrack, side: str, hits: list[float], stroke: str,
                 stroke_type: Optional[str]) -> tuple[Optional[str], Optional[dict]]:
    """The stroke type to coach, and the pose features when it was auto-detected.
    A chosen type wins; serve/flick map straight to a type; block/footwork have none;
    otherwise the type is read from the swing (within the given wing, if any)."""
    if stroke_type:
        return stroke_type, None
    if stroke in strokes.LEGACY_TYPE:
        return strokes.LEGACY_TYPE[stroke], None
    if stroke in ("block", "footwork"):
        return None, None
    _, p0 = key_moments(track, side, hits, direction="any")
    wing = stroke if stroke in ("forehand", "backhand") else None
    key, feats = strokes.detect(track, side, p0, wing=wing)
    return key, feats


def run_video(src: str, out_dir: str, stroke: str = "forehand", player: Optional[str] = None,
              analyzer: str = "auto", window: Optional[tuple[float, float]] = None,
              window_s: float = 8.0, t2v_provider: str = "none",
              progress: Optional[Progress] = None, hand: str = "auto",
              stroke_type: Optional[str] = None, trust_hand: bool = False) -> dict:
    """hand: auto | left | right (the player's bat hand, used when the paddle isn't visible;
    with trust_hand, always used).
    stroke: a broad stroke, or "" / "auto" to read it from the swing.
    stroke_type: a key of strokes.STROKE_TYPES, or None to auto-detect."""
    t0 = time.time()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stroke_type = strokes.resolve(stroke_type)
    auto = (stroke or "").strip().lower() in ("", "auto")
    stroke = "" if auto else normalize_stroke(stroke)
    info = media.probe(src)
    _log(progress, f"input {info['width']}x{info['height']} {info['duration']:.1f}s")

    identity = pose.initial_identity(src)
    if window:
        win = {"start": window[0], "end": window[1], "reason": "user"}
    else:
        win = choose_window(src, info["duration"], window_s, out, progress, identity=identity)
    _log(progress, f"window {win['start']:.1f}-{win['end']:.1f}s ({win['reason']})")

    clip = str(media.make_proxy(src, out / "clip.mp4", height=720, fps=30,
                                start=win["start"], end=win["end"]))
    _log(progress, "running MediaPipe pose")
    track = pose.extract_pose(clip, identity=identity)
    pose.require_player(track)
    hits = [h - win["start"] for h in win.get("hit_times", [])
            if win["start"] <= h <= win["end"]]
    side, how = pose.bat_side(clip, track, hand, trust_hand, hit_times=hits)
    _log(progress, f"bat hand: {side} ({how})")
    stroke_type, detected = _stroke_plan(track, side, hits, stroke, stroke_type)
    st = strokes.STROKE_TYPES.get(stroke_type or "")
    if st:
        stroke = st.stroke
        how_known = "auto-detected from the swing" if detected else "chosen"
        _log(progress, f"stroke type: {st.label} ({how_known})")
    stroke = stroke or "forehand"
    keys, peak_i = key_moments(track, side, hits, direction=st.direction if st else "up",
                               window_s=st.window_s if st else 0.6)
    summary = pose.summarize(track, side)
    contact = pose.pose_metrics(track, peak_i, side) if len(track.times) else {}
    (out / "pose_summary.json").write_text(json.dumps(summary, indent=2))
    pose.save_track(track, out / "pose_track.npz")

    dur = win["end"] - win["start"]
    frame_times = sorted(set([round(x, 2) for x in np.linspace(0.2, max(0.3, dur - 0.2), 6)] + keys))
    a = get_analyzer(analyzer)
    _log(progress, f"analysing with {a.name}")
    kind = dict(stroke_type=stroke_type, detected=detected is not None)
    try:
        if isinstance(a, OfflineAnalyzer):
            b = a.from_video(clip, stroke, frame_times, summary, keys, player,
                             contact_metrics=contact, **kind)
        else:
            b = a.from_video(clip, stroke, frame_times, summary, keys, player, **kind)
    except Exception as e:  # LLM failure must not kill the demo
        _log(progress, f"{a.name} failed ({e}); using offline analyzer")
        b = OfflineAnalyzer().from_video(clip, stroke, frame_times, summary, keys, player,
                                         contact_metrics=contact, **kind)
    if b.stroke_type not in strokes.STROKE_TYPES:  # Claude may correct a detected type
        b.stroke_type = stroke_type
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
        "stroke_type": b.stroke_type,
        "stroke_type_detected": detected,
        "window": {k: v for k, v in win.items() if k != "hit_times"},
        "analyzer": b.source,
        "bat_hand": {"side": side, "how": how},
        "key_times_s": keys,
        "contact_frame": int(peak_i),
        "outputs": {
            "breakdown_json": str(out / "breakdown.json"),
            "video_prompt_json": str(out / "video_prompt.json"),
            "pose_summary_json": str(out / "pose_summary.json"),
            "pose_track": str(out / "pose_track.npz"),
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
             progress: Optional[Progress] = None, stroke_type: Optional[str] = None) -> dict:
    t0 = time.time()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stroke_type = strokes.resolve(stroke_type)
    auto = (stroke or "").strip().lower() in ("", "auto")
    detected = None
    if not stroke_type and auto:
        stroke_type = strokes.from_text(text)
        detected = {"from": "text"} if stroke_type else None
    elif not stroke_type:
        stroke_type = strokes.LEGACY_TYPE.get(normalize_stroke(stroke))
    st = strokes.STROKE_TYPES.get(stroke_type or "")
    stroke = st.stroke if st else normalize_stroke(stroke)
    kind = dict(stroke_type=stroke_type, detected=detected is not None)
    a = get_analyzer(analyzer)
    try:
        b = a.from_text(text, stroke, player, **kind)
    except Exception as e:
        _log(progress, f"{a.name} failed ({e}); using offline analyzer")
        b = OfflineAnalyzer().from_text(text, stroke, player, **kind)
    if b.stroke_type not in strokes.STROKE_TYPES:
        b.stroke_type = stroke_type
    (out / "breakdown.json").write_text(b.model_dump_json(indent=2))
    prompts = build_prompts(b)
    (out / "video_prompt.json").write_text(json.dumps(prompts, indent=2))
    generated = generate_video(prompts, str(out / "generated.mp4"), t2v_provider)
    video = render_text_only(b, str(out / "breakdown.mp4"))
    result = {
        "kind": "technique_breakdown", "input": "text", "stroke": stroke, "analyzer": b.source,
        "stroke_type": b.stroke_type, "stroke_type_detected": detected,
        "outputs": {"breakdown_json": str(out / "breakdown.json"),
                    "video_prompt_json": str(out / "video_prompt.json"),
                    "overlay_video": video, "generated_video": generated},
        "elapsed_s": round(time.time() - t0, 1),
    }
    (out / "result.json").write_text(json.dumps(result, indent=2))
    return result
