from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from equipment import recommend as rubbers
from technique.strokes import STROKE_TYPES

from . import download, jobs, validate
from .pipelines import fetch_then, run_autocut, run_breakdown, run_match

app = FastAPI(title="TTSkill backend")
# Browsers call us directly from the Vercel frontend (uploads are over Vercel's 4.5 MB function limit),
# through a Cloudflare quick tunnel; localhost is for dev. Starlette full-matches the whole origin.
ALLOWED_ORIGINS = r"https://([a-z0-9-]+\.)+(vercel\.app|trycloudflare\.com)|http://(localhost|127\.0\.0\.1)(:\d+)?"
app.add_middleware(CORSMiddleware, allow_origin_regex=ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"])

STROKES = {"", "auto", "forehand", "backhand", "serve", "flick", "block", "footwork"}
# Friendly names for FastAPI's own type errors (e.g. top_n=abc), which would otherwise be a list of dicts.
LABELS = {"top_n": "Rallies in the reel", "threshold": "Hit threshold", "gap": "Max gap", "min_hits": "Min hits"}


@app.exception_handler(validate.Invalid)
@app.exception_handler(download.LinkError)
async def invalid_input(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(RequestValidationError)
async def bad_field(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Build the message from the field name only: echoing the input back can break the JSON encoding.
    err = exc.errors()[0]
    field = str(err["loc"][-1])
    label, kind = LABELS.get(field, field), err.get("type", "")
    msg = (f"{label} must be a whole number." if kind.startswith("int") else
           f"{label} must be a number." if kind.startswith("float") else
           f"{label} is missing." if kind == "missing" else f"{label} isn't valid.")
    return JSONResponse({"detail": msg}, status_code=422)


def save_upload(upload: UploadFile, dest: Path) -> Path:
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f, length=1024 * 1024)  # stream to disk
    return dest


def has_file(upload: UploadFile | None) -> bool:
    """Browsers send an empty, unnamed file part when the file input is left blank."""
    return upload is not None and bool(upload.filename) and upload.size != 0


def stage_upload(upload: UploadFile) -> Path:
    """Saves an upload outside any job and checks it (type, size, tracks, length,
    resolution), so a bad file is a 422 on the form and never creates a job."""
    suffix = validate.upload_name(upload.filename, upload.size)
    staging = jobs.DATA_DIR / ".uploads"
    staging.mkdir(parents=True, exist_ok=True)
    path = save_upload(upload, staging / f"{uuid.uuid4().hex}{suffix}")
    try:
        validate.video_file(path)
    except validate.Invalid:
        path.unlink(missing_ok=True)
        raise
    return path


def adopt(staged: Path, job_id: str) -> Path:
    """Moves a checked upload into its job folder as input.<ext>."""
    return staged.replace(jobs.job_dir(job_id) / f"input{staged.suffix}")


def check_link(url: str, kind: str) -> dict | None:
    """Probe a pasted link before the job starts, so bad links fail on the form (422)."""
    return download.probe(url, kind) if url.strip() else None


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/equipment/rubbers")
def get_rubbers(style: str = "spin", rubber_type: str = "inverted", level: str = "intermediate",
                budget: float = rubbers.DEFAULT_BUDGET, limit: int = 8) -> dict:
    """Rubber picks from the PingSense data within budget: $10 bands down from the budget, then user score."""
    if style not in rubbers.STYLES:
        raise HTTPException(400, "style must be spin or speed")
    if rubber_type not in rubbers.TYPES:
        raise HTTPException(400, "rubber type must be inverted, short_pips, long_pips or anti_spin")
    if level not in rubbers.LEVELS:
        raise HTTPException(400, "level must be beginner, intermediate or advanced")
    if not 0 < budget <= 500:
        raise HTTPException(400, "budget should be between $1 and $500")
    return rubbers.recommend(style, rubber_type, level, budget, max(1, min(limit, 20)))


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
    validate.choice(mode, "autocut_mode", "Mode")
    validate.in_range(top_n, "top_n", "Rallies in the reel")
    validate.in_range(threshold, "threshold", "Hit threshold")
    validate.in_range(gap, "gap", "Max gap")
    validate.in_range(min_hits, "min_hits", "Min hits")
    staged = stage_upload(video) if has_file(video) else None
    link = None if staged else check_link(url, "autocut")
    if not staged and link is None:
        raise validate.Invalid("Upload a match video or paste a YouTube link.")
    params = {"video": video.filename if staged else link["title"], "url": link and link["url"],
              "mode": mode, "top_n": top_n, "threshold": threshold, "gap": gap, "min_hits": min_hits}
    job = jobs.create("autocut", params)
    args = (mode, top_n, threshold, gap, min_hits)
    if link:
        background.add_task(jobs.run, fetch_then, job["id"], link["url"], run_autocut, *args)
    else:
        background.add_task(jobs.run, run_autocut, job["id"], adopt(staged, job["id"]), *args)
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
    player_time: str = Form(""),
    player_box: str = Form(""),
) -> dict:
    if stroke not in STROKES:
        raise validate.Invalid(f"Unknown stroke: {stroke}. Leave it blank to auto-detect.")
    if stroke_type and stroke_type not in STROKE_TYPES:
        raise validate.Invalid(f"Unknown stroke type: {stroke_type}. Pick one from the list, or leave it blank to auto-detect.")
    validate.choice(hand, "hand", "Bat hand")
    selection = validate.player_selection(player_time, player_box)
    player = validate.text(player, "player", "The player's name")
    text = validate.text(text, "training_text", "The training description")
    staged = stage_upload(video) if has_file(video) else None
    link = check_link(url, "breakdown") if staged is None else None
    if staged is None and link is None and not text:
        raise validate.Invalid("Upload a clip, paste a YouTube link, or describe the training.")
    params = {"stroke": stroke, "stroke_type": stroke_type or "auto", "player": player, "text": text, "hand": hand,
              "video": video.filename if staged else (link["title"] if link else None),
              "url": link and link["url"]}
    if selection and (staged or link):
        params["player_pick"] = {"time": selection[0], "box": list(selection[1])}
    job = jobs.create("breakdown", params)
    # The tapped player goes last, and only when there is one, so other calls are unchanged.
    args = (text, stroke, player, hand, stroke_type) + ((selection,) if selection and (staged or link) else ())
    if link:
        background.add_task(jobs.run, fetch_then, job["id"], link["url"], run_breakdown, *args)
    else:
        path = adopt(staged, job["id"]) if staged else None
        background.add_task(jobs.run, run_breakdown, job["id"], path, *args)
    return job


@app.post("/jobs/match", status_code=201)
def create_match(
    background: BackgroundTasks,
    stroke: str = Form("forehand"),
    hand: str = Form("auto"),
    grip: str = Form("shakehand"),
    height_cm: str = Form(""),
    video: UploadFile | None = File(None),
    url: str = Form(""),
    player_time: str = Form(""),
    player_box: str = Form(""),
) -> dict:
    validate.choice(stroke, "match_stroke", "Stroke")
    selection = validate.player_selection(player_time, player_box)
    validate.choice(hand, "hand", "Bat hand")
    validate.choice(grip, "grip", "Grip")
    height = validate.height_cm(height_cm)
    staged = stage_upload(video) if has_file(video) else None
    link = None if staged else check_link(url, "match")
    if not staged and link is None:
        raise validate.Invalid("Upload a clip of yourself or paste a YouTube link.")
    params = {"video": video.filename if staged else link["title"], "url": link and link["url"],
              "stroke": stroke, "hand": hand, "grip": grip, "height_cm": height}
    if selection:
        params["player_pick"] = {"time": selection[0], "box": list(selection[1])}
    job = jobs.create("match", params)
    args = (stroke, height, hand, grip) + ((selection,) if selection else ())
    if link:
        background.add_task(jobs.run, fetch_then, job["id"], link["url"], run_match, *args)
    else:
        background.add_task(jobs.run, run_match, job["id"], adopt(staged, job["id"]), *args)
    return job


@app.post("/jobs/coach", status_code=201)
def create_coach(
    background: BackgroundTasks,
    request: str = Form(""),
    video: UploadFile | None = File(None),
    url: str = Form(""),
    player_time: str = Form(""),
    player_box: str = Form(""),
) -> dict:
    """TT Coach: one request about one video, handled by the deep agent (agent/coach.py).
    Falls back to the classic pipelines when there is no API key or the agent fails."""
    from agent.coach import run_coach

    request = validate.text(request, "coach_request", "Your request")
    selection = validate.player_selection(player_time, player_box)
    if not request:
        raise validate.Invalid("Tell the coach what you want, e.g. 'show my best rallies and fix my forehand'.")
    staged = stage_upload(video) if has_file(video) else None
    link = None if staged else check_link(url, "coach")
    if not staged and link is None:
        raise validate.Invalid("Add a video: upload a clip or paste a YouTube link.")
    params = {"request": request, "video": video.filename if staged else link["title"],
              "url": link and link["url"]}
    if selection:
        params["player_pick"] = {"time": selection[0], "box": list(selection[1])}
    job = jobs.create("coach", params)
    path = adopt(staged, job["id"]) if staged else None
    background.add_task(jobs.run, run_coach, job["id"], path, link and link["url"], request,
                        *((selection,) if selection else ()))
    return job


@app.post("/players/detect")
def detect_players(
    frames: list[UploadFile] | None = File(None),
    times: str = Form(""),
    url: str = Form(""),
    kind: str = Form("breakdown"),
) -> dict:
    """The players in a few frames of the chosen video, for "Which one is you?". The browser
    sends frames it drew from the file (no second upload of the video); for a pasted link we
    download it and sample frames ourselves. `decisive` means no question is needed."""
    import cv2
    import numpy as np

    from technique import people

    if kind not in ("breakdown", "match", "coach"):
        raise validate.Invalid("kind must be breakdown, match or coach.")
    sent = [(f.filename, f.file.read()) for f in (frames or []) if has_file(f)]
    if sent or not url.strip():
        images = []
        for t, data in validate.player_frames(sent, times):
            image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise validate.Invalid("A frame couldn't be read as an image.")
            images.append((t, image))
        return people.detect(images)
    link = check_link(url, kind)
    folder = jobs.DATA_DIR / ".players" / uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=True)
    try:
        return people.detect(people.sample_frames(str(download.download(link["url"], folder))))
    finally:
        shutil.rmtree(folder, ignore_errors=True)   # the download is only for finding players


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
