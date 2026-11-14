"""Plain-function tools for the LangChain deepagents orchestrator.

Each tool takes/returns JSON-friendly values and works on a job directory, so an agent can
call them step by step (or skip straight to `technique_breakdown`). Register with e.g.

    from deepagents import create_deep_agent
    from technique.tools import TOOLS
    agent = create_deep_agent(tools=TOOLS, system_prompt="...")
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Optional

from . import audio, media, pose
from .analyze import OfflineAnalyzer, get_analyzer, normalize_stroke
from .pipeline import key_moments, run_text, run_video
from .render import render_breakdown as _render
from .schema import StrokeBreakdown
from .video_prompt import build_prompts


def technique_breakdown(video_path: str, job_dir: str, stroke: str = "forehand",
                        player: Optional[str] = None) -> dict:
    """Full pipeline on a video: finds the best rally, extracts pose, writes the stroke
    breakdown JSON + text-to-video prompt, and renders the vertical breakdown video."""
    return run_video(video_path, job_dir, stroke, player)


def technique_from_text(text: str, job_dir: str, stroke: str = "forehand",
                        player: Optional[str] = None) -> dict:
    """Breakdown from a text description of a player's training (no video)."""
    return run_text(text, job_dir, stroke, player)


def find_rallies(video_path: str) -> list[dict]:
    """Rallies detected from ball-contact sounds: [{start, end, hits}], seconds."""
    return [{k: r[k] for k in ("start", "end", "hits")} for r in audio.find_rallies(video_path)]


def extract_pose(video_path: str, job_dir: str, start: float, end: float) -> dict:
    """Cut [start, end] to a 720p clip, run MediaPipe pose, and save it in job_dir.
    Returns the pose summary (bat hand, swing peaks, joint angles)."""
    out = Path(job_dir)
    out.mkdir(parents=True, exist_ok=True)
    clip = media.make_proxy(video_path, out / "clip.mp4", start=start, end=end)
    tr = pose.extract_pose(clip)
    with open(out / "pose.pkl", "wb") as f:
        pickle.dump(tr, f)
    side = pose.dominant_side(tr)
    summary = pose.summarize(tr, side if side != "unknown" else "right")
    (out / "pose_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def analyze_technique(job_dir: str, stroke: str = "forehand", player: Optional[str] = None) -> dict:
    """Run the vision analyzer on the clip + pose saved by extract_pose. Returns the
    StrokeBreakdown (grip, stance, swing path, contact point, 3 steps) and the video prompt."""
    out = Path(job_dir)
    with open(out / "pose.pkl", "rb") as f:
        tr = pickle.load(f)
    side = pose.dominant_side(tr)
    side = side if side != "unknown" else "right"
    keys, pi = key_moments(tr, side)
    summary = pose.summarize(tr, side)
    clip = str(out / "clip.mp4")
    stroke = normalize_stroke(stroke)
    a = get_analyzer()
    times = sorted(set(keys + [float(t) for t in tr.times[:: max(1, len(tr.times) // 6)]]))
    if isinstance(a, OfflineAnalyzer):
        b = a.from_video(clip, stroke, times, summary, keys, player,
                         contact_metrics=pose.pose_metrics(tr, pi, side))
    else:
        b = a.from_video(clip, stroke, times, summary, keys, player)
    (out / "breakdown.json").write_text(b.model_dump_json(indent=2))
    prompts = build_prompts(b)
    (out / "video_prompt.json").write_text(json.dumps(prompts, indent=2))
    return {"breakdown": json.loads(b.model_dump_json()), "video_prompt": prompts["prompt"]}


def render_breakdown(job_dir: str) -> str:
    """Render breakdown.mp4 (1080x1920) from the clip, pose and breakdown in job_dir."""
    out = Path(job_dir)
    with open(out / "pose.pkl", "rb") as f:
        tr = pickle.load(f)
    b = StrokeBreakdown.model_validate_json((out / "breakdown.json").read_text())
    side = pose.dominant_side(tr)
    return _render(str(out / "clip.mp4"), tr, b, str(out / "breakdown.mp4"),
                   side if side != "unknown" else "right")


TOOLS = [technique_breakdown, technique_from_text, find_rallies, extract_pose,
         analyze_technique, render_breakdown]
