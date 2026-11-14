"""Plain (non-agent) pipelines. The deepagents wrapper will call these same steps as tools."""
from __future__ import annotations

import json
import shutil
import traceback
from pathlib import Path

from . import jobs
from .rally import detect_rallies


def run_autocut(job_id: str, video: Path, mode: str, top_n: int, threshold: float, gap: float, min_hits: int) -> None:
    try:
        jobs.update(job_id, status="running", progress=0.1, message="Listening for ball contacts...")
        rallies = detect_rallies(video, jobs.job_dir(job_id), threshold, gap, min_hits)
        if mode == "highlights":
            rallies = sorted(rallies, key=lambda r: -r.hits)[:top_n]
        # TODO: transcode proxy, pad each rally 1.5 s, cut and concat with ffmpeg, set resultUrl.
        jobs.update(job_id, status="done", progress=1.0,
                    message=f"Found {len(rallies)} rallies. Cutting is not implemented yet.",
                    rallies=[r.to_dict() for r in rallies])
    except Exception as exc:  # surface errors on the job page
        traceback.print_exc()
        jobs.update(job_id, status="failed", message=str(exc))


# Rough progress for each pipeline log line, so the job page bar moves.
_STAGES = [("input", 0.1), ("longest rally", 0.2), ("no rallies", 0.2), ("window", 0.25),
           ("running MediaPipe", 0.35), ("bat hand", 0.5), ("analysing", 0.6),
           ("rendering", 0.8), ("done", 0.95)]


def _progress(job_id: str):
    state = {"p": 0.05}

    def report(msg: str) -> None:
        for prefix, p in _STAGES:
            if msg.startswith(prefix):
                state["p"] = max(state["p"], p)
                break
        jobs.update(job_id, status="running", progress=state["p"], message=msg)
    return report


def run_breakdown(job_id: str, video: Path | None, text: str, stroke: str, player: str,
                  hand: str = "auto") -> None:
    """Runs backend/technique and copies its breakdown.mp4 to result.mp4 for the job page."""
    try:
        from technique.pipeline import run_text, run_video  # heavy imports (MediaPipe, OpenCV)

        out = jobs.job_dir(job_id) / "technique"
        report = _progress(job_id)
        report("starting technique pipeline")
        if video is not None:
            res = run_video(str(video), str(out), stroke, player or None, progress=report, hand=hand)
        else:
            res = run_text(text, str(out), stroke, player or None, progress=report)
        overlay = Path(res["outputs"]["overlay_video"])
        shutil.copyfile(overlay, jobs.job_dir(job_id) / "result.mp4")
        breakdown = json.loads((out / "breakdown.json").read_text())
        prompt_path = out / "video_prompt.json"
        video_prompt = json.loads(prompt_path.read_text()) if prompt_path.exists() else None
        jobs.update(job_id, status="done", progress=1.0,
                    message=f"{breakdown.get('headline') or 'Breakdown ready'} ({res['analyzer']} analyzer)",
                    resultUrl=f"/jobs/{job_id}/result", breakdown=breakdown,
                    videoPrompt=video_prompt, analyzer=res["analyzer"],
                    batHand=res.get("bat_hand"), window=res.get("window"))
    except Exception as exc:  # surface errors on the job page
        traceback.print_exc()
        jobs.update(job_id, status="failed", message=str(exc))
