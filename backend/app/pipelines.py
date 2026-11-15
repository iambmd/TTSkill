"""Plain (non-agent) pipelines. The deepagents wrapper will call these same steps as tools."""
from __future__ import annotations

import json
import shutil
import traceback
from pathlib import Path
from typing import Callable

from . import jobs
from .cut import cut_and_concat, duration, padded_segments
from .download import download
from .rally import detect_rallies


def fetch_then(job_id: str, url: str, run: Callable[..., None], *args) -> None:
    """Downloads a pasted link into the job folder as the upload would be, runs the normal
    pipeline on it, then deletes the full download (the result video stays)."""
    seen = {"pct": -1}

    def report(f: float) -> None:
        pct = int(f * 100)
        if pct >= seen["pct"] + 5:  # yt-dlp reports many times a second
            seen["pct"] = pct
            jobs.update(job_id, progress=round(0.05 * f, 3), message=f"Downloading the video... {pct}%")

    try:
        jobs.update(job_id, status="running", progress=0.0, message="Downloading the video...")
        path = download(url, jobs.job_dir(job_id), progress=report)
    except Exception as exc:  # LinkError messages are written for the user
        traceback.print_exc()
        jobs.update(job_id, status="failed", progress=1.0, message=str(exc))
        return
    try:
        run(job_id, path, *args)
    finally:
        path.unlink(missing_ok=True)


def run_autocut(job_id: str, video: Path, mode: str, top_n: int, threshold: float, gap: float, min_hits: int) -> None:
    try:
        jobs.update(job_id, status="running", progress=0.1, message="Listening for ball contacts...")
        workdir = jobs.job_dir(job_id)
        found = detect_rallies(video, workdir, threshold, gap, min_hits)
        if found:
            jobs.update(job_id, progress=0.2, message="Checking for pre-serve floor bounces...")
            from .floor_bounce import drop_floor_bounces  # heavy imports (MediaPipe, OpenCV)
            found, bounces = drop_floor_bounces(video, found)
            if bounces:
                print(f"dropped {len(bounces)} floor-bounce spans: {[r.to_dict() for r in bounces]}")
        if not found:
            jobs.update(job_id, status="failed", progress=1.0, rallies=[],
                        message="No rallies found. Try a lower hit threshold or fewer min hits.")
            return
        if mode == "highlights":
            # Best rallies first; padding never merges them so each stays its own clip.
            rallies = sorted(found, key=lambda r: -r.hits)[:top_n]
            segments = padded_segments([(r.start, r.end) for r in rallies], duration(video), merge=False)
        else:
            rallies = found
            segments = padded_segments([(r.start, r.end) for r in rallies], duration(video))
        jobs.update(job_id, progress=0.3, message=f"Found {len(found)} rallies. Cutting {len(segments)} clips...",
                    rallies=[r.to_dict() for r in rallies])
        cut_and_concat(video, segments, workdir, workdir / "result.mp4",
                       progress=lambda f: jobs.update(job_id, progress=round(0.3 + 0.65 * f, 3)))
        length = sum(e - s for s, e in segments)
        label = f"Top {len(rallies)} rallies" if mode == "highlights" else f"All {len(rallies)} rallies"
        jobs.update(job_id, status="done", progress=1.0, resultUrl=f"/jobs/{job_id}/result",
                    message=f"{label}, {length:.0f} s cut from {len(found)} detected.")
    except Exception as exc:  # surface errors on the job page
        traceback.print_exc()
        jobs.update(job_id, status="failed", message=str(exc))


# Rough progress for each pipeline log line, so the job page bar moves.
_STAGES = [("input", 0.1), ("longest rally", 0.2), ("no rallies", 0.2), ("window", 0.25),
           ("running MediaPipe", 0.35), ("bat hand", 0.5), ("stroke type", 0.55), ("analysing", 0.6),
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
                  hand: str = "auto", stroke_type: str = "") -> None:
    """Runs backend/technique and copies its breakdown.mp4 to result.mp4 for the job page."""
    try:
        from technique.pipeline import run_text, run_video  # heavy imports (MediaPipe, OpenCV)
        from technique.strokes import label

        out = jobs.job_dir(job_id) / "technique"
        report = _progress(job_id)
        report("starting technique pipeline")
        if video is not None:
            res = run_video(str(video), str(out), stroke, player or None, progress=report, hand=hand,
                            stroke_type=stroke_type or None)
        else:
            res = run_text(text, str(out), stroke, player or None, progress=report,
                           stroke_type=stroke_type or None)
        overlay = Path(res["outputs"]["overlay_video"])
        shutil.copyfile(overlay, jobs.job_dir(job_id) / "result.mp4")
        breakdown = json.loads((out / "breakdown.json").read_text())
        prompt_path = out / "video_prompt.json"
        video_prompt = json.loads(prompt_path.read_text()) if prompt_path.exists() else None
        jobs.update(job_id, status="done", progress=1.0,
                    message=f"{breakdown.get('headline') or 'Breakdown ready'} ({res['analyzer']} analyzer)",
                    resultUrl=f"/jobs/{job_id}/result", breakdown=breakdown,
                    videoPrompt=video_prompt, analyzer=res["analyzer"],
                    batHand=res.get("bat_hand"), window=res.get("window"),
                    strokeType={"key": res.get("stroke_type"), "label": label(res.get("stroke_type") or res["stroke"]),
                                "detected": res.get("stroke_type_detected") is not None,
                                "features": res.get("stroke_type_detected")})
    except Exception as exc:  # surface errors on the job page
        traceback.print_exc()
        jobs.update(job_id, status="failed", message=str(exc))


def run_match(job_id: str, video: Path, stroke: str, height_cm: float | None = None,
              hand: str = "auto") -> None:
    """Find my pro match: pose on the user's clip, body profile, height (entered or from the
    table), top 3 pros with the same bat hand, form differences, one compiled video."""
    try:
        from players.body import angle_curves, body_ratios
        from players.compile import compile_matches
        from players.match import match
        from players.table import estimate_height_cm
        from technique import media, pose
        from technique.pipeline import choose_window, key_moments

        out = jobs.job_dir(job_id) / "match"
        out.mkdir(parents=True, exist_ok=True)
        jobs.update(job_id, status="running", progress=0.1, message="Finding your best swings...")
        info = media.probe(video)
        win = choose_window(str(video), info["duration"], 8.0, out, progress=lambda m: None)
        clip = media.make_proxy(video, out / "clip.mp4", height=720, fps=30, start=win["start"], end=win["end"])
        jobs.update(job_id, progress=0.3, message="Reading your body and swing with MediaPipe...")
        track = pose.extract_pose(clip)
        if not track.valid.any():
            raise RuntimeError("No player found in the video. Film the whole body, side-on if you can.")
        side, how = pose.bat_side(clip, track, hand)
        hits = [h - win["start"] for h in win.get("hit_times", []) if win["start"] <= h <= win["end"]]
        _, contact = key_moments(track, side, hits, direction="up")
        body = body_ratios(track)
        curves = angle_curves(track, side, contact)
        if height_cm:
            height = {"height_cm": round(height_cm), "method": "entered"}
        else:
            jobs.update(job_id, progress=0.55, message="Estimating your height from the table...")
            height = estimate_height_cm(str(clip), track)
        user = {**body, "height_cm": height["height_cm"] if height else None}
        jobs.update(job_id, progress=0.65, message="Comparing you with the pros...")
        matches = match(user, curves, stroke, side)
        if not matches:
            raise RuntimeError("No pro profiles are built yet. Run: python -m players.build")
        jobs.update(job_id, progress=0.75, message="Putting their breakdowns together...")
        result = compile_matches(matches, stroke, out / "parts", jobs.job_dir(job_id) / "result.mp4")
        top = matches[0]
        jobs.update(job_id, status="done", progress=1.0,
                    message=f"You play most like {top['name']} ({top['score']}% body match).",
                    resultUrl=f"/jobs/{job_id}/result" if result else None,
                    matches=[{k: v for k, v in m.items() if k != "form"} for m in matches],
                    you={"bat_hand": side, "bat_hand_how": how, "height": height,
                         "body": {k: v for k, v in body.items() if k not in ("height_units", "units")}})
    except Exception as exc:  # surface errors on the job page
        traceback.print_exc()
        jobs.update(job_id, status="failed", message=str(exc))
