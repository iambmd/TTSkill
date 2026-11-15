from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import download, jobs
from .pipelines import fetch_then, run_autocut, run_breakdown

app = FastAPI(title="TTSkill backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STROKES = {"forehand", "backhand", "serve", "flick", "block", "footwork"}


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
        background.add_task(fetch_then, job["id"], link["url"], run_autocut, *args)
    else:
        path = save_upload(video, jobs.job_dir(job["id"]) / f"input{Path(video.filename or '').suffix}")
        background.add_task(run_autocut, job["id"], path, *args)
    return job


@app.post("/jobs/breakdown", status_code=201)
def create_breakdown(
    background: BackgroundTasks,
    stroke: str = Form(...),
    text: str = Form(""),
    player: str = Form(""),
    hand: str = Form("auto"),
    video: UploadFile | None = File(None),
    url: str = Form(""),
) -> dict:
    if stroke not in STROKES:
        raise HTTPException(400, f"unknown stroke: {stroke}")
    if hand not in ("auto", "left", "right"):
        raise HTTPException(400, "hand must be auto, left or right")
    if not has_file(video):
        video = None
    link = check_link(url) if video is None else None
    if video is None and link is None and not text.strip():
        raise HTTPException(400, "Upload a clip, paste a YouTube link, or describe the training.")
    params = {"stroke": stroke, "player": player, "text": text, "hand": hand,
              "video": video.filename if video else (link["title"] if link else None),
              "url": link and link["url"]}
    job = jobs.create("breakdown", params)
    args = (text, stroke, player, hand)
    if link:
        background.add_task(fetch_then, job["id"], link["url"], run_breakdown, *args)
    else:
        path = save_upload(video, jobs.job_dir(job["id"]) / f"input{Path(video.filename or '').suffix}") if video else None
        background.add_task(run_breakdown, job["id"], path, *args)
    return job


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = jobs.load(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


@app.get("/jobs/{job_id}/result")
def get_result(job_id: str) -> FileResponse:
    path = jobs.job_dir(job_id) / "result.mp4"
    if not path.exists():
        raise HTTPException(404, "no result yet")
    return FileResponse(path, media_type="video/mp4", filename=f"ttskill-{job_id}.mp4")
