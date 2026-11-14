from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import jobs
from .pipelines import run_autocut, run_breakdown

app = FastAPI(title="TTSkill backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STROKES = {"forehand", "backhand", "serve", "flick", "block", "footwork"}


def save_upload(upload: UploadFile, dest: Path) -> Path:
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f, length=1024 * 1024)  # stream to disk
    return dest


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/jobs/autocut", status_code=201)
def create_autocut(
    background: BackgroundTasks,
    video: UploadFile = File(...),
    mode: str = Form("highlights"),
    top_n: int = Form(5),
    threshold: float = Form(3.0),
    gap: float = Form(1.6),
    min_hits: int = Form(4),
) -> dict:
    if mode not in ("highlights", "full"):
        raise HTTPException(400, "mode must be 'highlights' or 'full'")
    params = {"video": video.filename, "mode": mode, "top_n": top_n, "threshold": threshold, "gap": gap, "min_hits": min_hits}
    job = jobs.create("autocut", params)
    path = save_upload(video, jobs.job_dir(job["id"]) / f"input{Path(video.filename or '').suffix}")
    background.add_task(run_autocut, job["id"], path, mode, top_n, threshold, gap, min_hits)
    return job


@app.post("/jobs/breakdown", status_code=201)
def create_breakdown(
    background: BackgroundTasks,
    stroke: str = Form(...),
    text: str = Form(""),
    player: str = Form(""),
    video: UploadFile | None = File(None),
) -> dict:
    if stroke not in STROKES:
        raise HTTPException(400, f"unknown stroke: {stroke}")
    if video is None and not text.strip():
        raise HTTPException(400, "provide a video or a text description")
    params = {"stroke": stroke, "player": player, "text": text, "video": video.filename if video else None}
    job = jobs.create("breakdown", params)
    path = save_upload(video, jobs.job_dir(job["id"]) / f"input{Path(video.filename or '').suffix}") if video else None
    background.add_task(run_breakdown, job["id"], path, text, stroke, player)
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
