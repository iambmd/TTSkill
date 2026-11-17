"""Plain (non-agent) pipelines. The deepagents wrapper will call these same steps as tools."""
from __future__ import annotations

import json
import shutil
import traceback
from pathlib import Path
from typing import Callable

from limits import LIMITS

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


def pick_segments(found: list, video: Path, mode: str, top_n: int) -> tuple[list, list[tuple[float, float]]]:
    """Rallies to keep and their padded segments. Highlights: best rallies first, padding
    never merges them so each stays its own clip. Full: every rally, overlaps merged."""
    rallies = sorted(found, key=lambda r: -r.hits)[:top_n] if mode == "highlights" else found
    total = duration(video)
    return rallies, padded_segments([(r.start, r.end) for r in rallies], total,
                                    merge=mode != "highlights",
                                    bounds=[r.clip_bounds or (0.0, total) for r in rallies])


def few_rallies_warning(count: int) -> str | None:
    """Advice when the sound gave fewer rallies than a useful cut needs (shared/limits.json)."""
    if count >= LIMITS["autocut"]["min_rallies"]:
        return None
    heard = ("We didn't hear any rallies" if count == 0 else
             f"We only heard {count} rall{'y' if count == 1 else 'ies'}")
    return (f"{heard}. Film closer to the table, or somewhere with less background noise, so each "
            "ball contact is clear. You can also lower the hit threshold under Detection settings.")


def run_autocut(job_id: str, video: Path, mode: str, top_n: int, threshold: float, gap: float, min_hits: int) -> None:
    try:
        jobs.update(job_id, status="running", progress=0.1, message="Listening for ball contacts...")
        workdir = jobs.job_dir(job_id)
        found = detect_rallies(video, workdir, threshold, gap, min_hits)
        if found:
            jobs.update(job_id, progress=0.2, message="Checking each rally shows real play...")
            from .floor_bounce import drop_non_play  # heavy imports (MediaPipe, OpenCV)
            found, bounces = drop_non_play(video, found, min_hits=min_hits)
            if bounces:
                print(f"dropped {len(bounces)} non-play spans: {[r.to_dict() for r in bounces]}")
        warning = few_rallies_warning(len(found))  # counted after non-play spans are dropped
        if not found:  # nothing to cut, but the advice is the result: done, not failed
            jobs.update(job_id, status="done", progress=1.0, rallies=[], warning=warning,
                        message="No rallies found.")
            return
        rallies, segments = pick_segments(found, video, mode, top_n)
        jobs.update(job_id, progress=0.3, message=f"Found {len(found)} rallies. Cutting {len(segments)} clips...",
                    rallies=[r.to_dict() for r in rallies])
        cut_and_concat(video, segments, workdir, workdir / "result.mp4",
                       progress=lambda f: jobs.update(job_id, progress=round(0.3 + 0.65 * f, 3)))
        length = sum(e - s for s, e in segments)
        label = f"Top {len(rallies)} rallies" if mode == "highlights" else f"All {len(rallies)} rallies"
        jobs.update(job_id, status="done", progress=1.0, resultUrl=f"/jobs/{job_id}/result", warning=warning,
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


def match_video(video: Path, stroke: str, out: Path, dest: Path, height_cm: float | None = None,
                hand: str = "auto", report: Callable[[float, str], None] = lambda p, m: None,
                grip: str | None = None) -> dict:
    """Find my pro match core, shared by the /jobs/match pipeline and the coach agent:
    pose on the user's clip, body profile, height (entered or from the table), top 3 pros
    with the same bat hand (and grip first, when given), form differences, and one
    compiled video at `dest`."""
    from players.body import angle_curves, body_ratios
    from players.compile import compile_matches
    from players.match import match
    from players.table import estimate_height_cm
    from technique import media, pose
    from technique.pipeline import choose_window, key_moments

    out.mkdir(parents=True, exist_ok=True)
    report(0.1, "Finding your best swings...")
    info = media.probe(video)
    # Same player selection as Breakdown and Coach: the person nearest at the start, kept
    # by appearance, so a bigger opponent later in the clip is never measured instead.
    identity = pose.initial_identity(video)
    win = choose_window(str(video), info["duration"], 8.0, out, progress=lambda m: None, identity=identity)
    clip = media.make_proxy(video, out / "clip.mp4", height=720, fps=30, start=win["start"], end=win["end"])
    report(0.3, "Reading your body and swing with MediaPipe...")
    track = pose.extract_pose(clip, identity=identity)
    pose.require_player(track)
    hits = [h - win["start"] for h in win.get("hit_times", []) if win["start"] <= h <= win["end"]]
    side, how = pose.bat_side(clip, track, hand, hit_times=hits)
    _, contact = key_moments(track, side, hits, direction="up")
    body = body_ratios(track)
    curves = angle_curves(track, side, contact)
    if height_cm:
        height = {"height_cm": round(height_cm), "method": "entered"}
    else:
        report(0.55, "Estimating your height from the table...")
        height = estimate_height_cm(str(clip), track)
    user = {**body, "height_cm": height["height_cm"] if height else None}
    report(0.65, "Comparing you with the pros...")
    matches = match(user, curves, stroke, side, grip=grip)
    if not matches:
        raise RuntimeError("No pro profiles are built yet. Run: python -m players.build")
    report(0.75, "Putting their breakdowns together...")
    result = compile_matches(matches, stroke, out / "parts", dest)
    return {"matches": [{k: v for k, v in m.items() if k != "form"} for m in matches],
            "you": {"bat_hand": side, "bat_hand_how": how, "height": height,
                    "body": {k: v for k, v in body.items() if k not in ("height_units", "units")}},
            "video": str(result) if result else None}


def run_match(job_id: str, video: Path, stroke: str, height_cm: float | None = None,
              hand: str = "auto", grip: str | None = None) -> None:
    try:
        jobs.update(job_id, status="running", progress=0.05, message="Starting...")
        res = match_video(video, stroke, jobs.job_dir(job_id) / "match", jobs.job_dir(job_id) / "result.mp4",
                          height_cm, hand, report=lambda p, m: jobs.update(job_id, progress=p, message=m),
                          grip=grip)
        top = res["matches"][0]
        jobs.update(job_id, status="done", progress=1.0,
                    message=f"You play most like {top['name']} ({top['score']}% body match).",
                    resultUrl=f"/jobs/{job_id}/result" if res["video"] else None,
                    matches=res["matches"], you=res["you"])
    except Exception as exc:  # surface errors on the job page
        traceback.print_exc()
        jobs.update(job_id, status="failed", message=str(exc))
