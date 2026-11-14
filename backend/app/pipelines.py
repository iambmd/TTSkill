"""Plain (non-agent) pipelines. The deepagents wrapper will call these same steps as tools."""
from __future__ import annotations

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


def run_breakdown(job_id: str, video: Path | None, text: str, stroke: str, player: str) -> None:
    # TODO: pose extraction (MediaPipe), Claude analysis, render vertical breakdown video.
    jobs.update(job_id, status="done", progress=1.0,
                message=f"Stub: {stroke} breakdown for {player or 'player'} is not implemented yet.")
