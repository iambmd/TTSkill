from __future__ import annotations

import shutil
import re
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from technique.strokes import STROKE_TYPES

from . import download, jobs
from .pipelines import fetch_then, run_autocut, run_breakdown, run_match

app = FastAPI(title="TTSkill backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STROKES = {"", "auto", "forehand", "backhand", "serve", "flick", "block", "footwork"}


def save_upload(upload: UploadFile, dest: Path) -> Path:
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f, length=1024 * 1024)  # stream to disk
    return dest


def has_file(upload: UploadFile | None) -> bool:
    """Browsers send an empty, unnamed file part when the file input is left blank."""
    return upload is not None and bool(upload.filename) and upload.size != 0


def check_link(url: str) -> dict | None:
    """Probe a pasted link before the job starts, so bad links fail on the form."""
    if not url.strip():
        return None
    try:
        return download.probe(url)
    except download.LinkError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/jobs/autocut", status_code=201)
def create_autocut(
    background: BackgroundTasks,
    video: UploadFile | None = File(None),
    url: str = Form(""),
    mode: str = Form("highlights"),
    top_n: int = Form(5),
    threshold: float = Form(3.0),
    gap: float = Form(1.6),
    min_hits: int = Form(4),
) -> dict:
    if mode not in ("highlights", "full"):
        raise HTTPException(400, "mode must be 'highlights' or 'full'")
    link = None if has_file(video) else check_link(url)
    if not has_file(video) and link is None:
        raise HTTPException(400, "Upload a match video or paste a YouTube link.")
    params = {"video": video.filename if link is None else link["title"], "url": link and link["url"],
              "mode": mode, "top_n": top_n, "threshold": threshold, "gap": gap, "min_hits": min_hits}
    job = jobs.create("autocut", params)
    args = (mode, top_n, threshold, gap, min_hits)
    if link:
        background.add_task(jobs.run, fetch_then, job["id"], link["url"], run_autocut, *args)
    else:
        path = save_upload(video, jobs.job_dir(job["id"]) / f"input{Path(video.filename or '').suffix}")
        background.add_task(jobs.run, run_autocut, job["id"], path, *args)
    return job


@app.post("/jobs/breakdown", status_code=201)
def create_breakdown(
    background: BackgroundTasks,
    stroke: str = Form(""),
    stroke_type: str = Form(""),
    text: str = Form(""),
    player: str = Form(""),
    hand: str = Form("auto"),
    video: UploadFile | None = File(None),
    url: str = Form(""),
) -> dict:
    if stroke not in STROKES:
        raise HTTPException(400, f"unknown stroke: {stroke}")
    if stroke_type and stroke_type not in STROKE_TYPES:
        raise HTTPException(400, f"unknown stroke type: {stroke_type}")
    if hand not in ("auto", "left", "right"):
        raise HTTPException(400, "hand must be auto, left or right")
    if not has_file(video):
        video = None
    link = check_link(url) if video is None else None
    if video is None and link is None and not text.strip():
        raise HTTPException(400, "Upload a clip, paste a YouTube link, or describe the training.")
    params = {"stroke": stroke, "stroke_type": stroke_type or "auto", "player": player, "text": text, "hand": hand,
              "video": video.filename if video else (link["title"] if link else None),
              "url": link and link["url"]}
    job = jobs.create("breakdown", params)
    args = (text, stroke, player, hand, stroke_type)
    if link:
        background.add_task(jobs.run, fetch_then, job["id"], link["url"], run_breakdown, *args)
    else:
        path = save_upload(video, jobs.job_dir(job["id"]) / f"input{Path(video.filename or '').suffix}") if video else None
        background.add_task(jobs.run, run_breakdown, job["id"], path, *args)
    return job


@app.post("/jobs/match", status_code=201)
def create_match(
    background: BackgroundTasks,
    stroke: str = Form("forehand"),
    hand: str = Form("auto"),
    height_cm: str = Form(""),
    video: UploadFile | None = File(None),
    url: str = Form(""),
) -> dict:
    if stroke not in ("forehand", "backhand"):
        raise HTTPException(400, "stroke must be forehand or backhand")
    if hand not in ("auto", "left", "right"):
        raise HTTPException(400, "hand must be auto, left or right")
    try:
        height = float(height_cm) if height_cm.strip() else None
    except ValueError:
        raise HTTPException(400, "height must be a number in cm") from None
    if height is not None and not 100 <= height <= 230:
        raise HTTPException(400, "height should be between 100 and 230 cm")
    link = None if has_file(video) else check_link(url)
    if not has_file(video) and link is None:
        raise HTTPException(400, "Upload a clip of yourself or paste a YouTube link.")
    params = {"video": video.filename if link is None else link["title"], "url": link and link["url"],
              "stroke": stroke, "hand": hand, "height_cm": height}
    job = jobs.create("match", params)
    args = (stroke, height, hand)
    if link:
        background.add_task(jobs.run, fetch_then, job["id"], link["url"], run_match, *args)
    else:
        path = save_upload(video, jobs.job_dir(job["id"]) / f"input{Path(video.filename or '').suffix}")
        background.add_task(jobs.run, run_match, job["id"], path, *args)
    return job


@app.post("/jobs/coach", status_code=201)
def create_coach(
    background: BackgroundTasks,
    request: str = Form(...),
    video: UploadFile | None = File(None),
    url: str = Form(""),
) -> dict:
    """TT Coach: one request about one video, handled by the deep agent (agent/coach.py).
    Falls back to the classic pipelines when there is no API key or the agent fails."""
    from agent.coach import run_coach

    request = request.strip()
    if not request:
        raise HTTPException(400, "Tell the coach what you want, e.g. 'show my best rallies and fix my forehand'.")
    link = None if has_file(video) else check_link(url)
    if not has_file(video) and link is None:
        raise HTTPException(400, "Add a video: upload a clip or paste a YouTube link.")
    params = {"request": request, "video": video.filename if link is None else link["title"],
              "url": link and link["url"]}
    job = jobs.create("coach", params)
    path = None
    if not link:
        path = save_upload(video, jobs.job_dir(job["id"]) / f"input{Path(video.filename or '').suffix}")
    background.add_task(jobs.run, run_coach, job["id"], path, link and link["url"], request)
    return job


@app.get("/jobs/{job_id}/files/{name}")
def get_file(job_id: str, name: str) -> FileResponse:
    """Videos the coach agent made (highlights.mp4, breakdown.mp4, pro_matches.mp4)."""
    if not re.fullmatch(r"[\w-]{1,64}\.mp4", name) or not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise HTTPException(404, "not found")
    path = jobs.job_dir(job_id) / name
    if not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path, media_type="video/mp4", filename=f"ttskill-{name}")


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


@app.get("/jobs/{job_id}/result")
def get_result(job_id: str) -> FileResponse:
    path = jobs.job_dir(job_id) / "result.mp4"
    if not path.exists():
        raise HTTPException(404, "no result yet")
    return FileResponse(path, media_type="video/mp4", filename=f"ttskill-{job_id}.mp4")
