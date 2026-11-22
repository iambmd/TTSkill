from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import BackgroundTasks, Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from pydantic import StrictInt

from equipment import recommend as rubbers
from technique.strokes import STROKE_TYPES

from . import download, jobqueue, jobs, validate
from .cut import concat_parts
from .pipelines import fetch_then, run_autocut, run_breakdown, run_match

log = logging.getLogger("uvicorn.error")   # configured by uvicorn, so INFO lines show in `make backend`


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("TTSKILL_WARM", "1") != "0":
        warm_players()
    yield


app = FastAPI(title="TTSkill backend", lifespan=lifespan)
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


STAGED_HOURS = 2   # an upload kept for its job after "Which one is you?" (see staged_input)


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


def keep_for_job(path: Path, filename: str) -> str:
    """Keep a staged upload for the job that follows ("Which one is you?" read its frames on
    the server because the browser couldn't): the form sends this token instead of the file,
    so a big phone video goes up once. Older kept uploads are deleted here."""
    cutoff = time.time() - STAGED_HOURS * 3600
    for old in path.parent.glob("*"):
        if old.stat().st_mtime < cutoff:
            old.unlink(missing_ok=True)
    path.with_name(path.name + ".name").write_text(filename or path.name)
    return path.name


def staged_input(token: str) -> tuple[Path, str]:
    """The upload a `staged` token names, and its original file name."""
    if not re.fullmatch(r"[0-9a-f]{32}\.(mp4|mov|webm|mkv)", token):
        raise validate.Invalid("Choose the video again.")
    path = jobs.DATA_DIR / ".uploads" / token
    if not path.exists():
        raise validate.Invalid("Your upload expired. Choose the video again.")
    name = path.with_name(token + ".name")
    filename = name.read_text() if name.exists() else token
    name.unlink(missing_ok=True)
    return path, filename


def take_video(video: UploadFile | None, staged: str) -> tuple[Path | None, str | None]:
    """The job's upload: one already on the server (`staged`), else the file sent now."""
    if staged.strip():
        return staged_input(staged.strip())
    if has_file(video):
        return stage_upload(video), video.filename
    return None, None


def uploaded_match(source_job: str, source_rally: str = "") -> tuple[Path, str]:
    """Reuse the original upload or a published rally from a finished Auto-Cut job."""
    path = job_input(source_job)
    source = jobs.load(source_job)
    if not source or source["kind"] != "autocut" or source["status"] != "done":
        raise validate.Invalid("Open a finished match result to use that video.")
    if source_rally:
        ids = {str(rally["id"]) for rally in source.get("rallyClips", [])}
        if source_rally not in ids:
            raise validate.Invalid("That rally is no longer available. Open the match result and choose again.")
        path = jobs.job_dir(source_job) / f"rally-{source_rally}.mp4"
    if not path or not path.is_file():
        raise validate.Invalid("This video is no longer available. Choose the video again.")
    return path, source["params"].get("video") or path.name


def analysis_input(path: Path, job_id: str, source_job: str) -> Path:
    if not source_job:
        return adopt(path, job_id)
    dest = jobs.job_dir(job_id) / f"input{path.suffix}"
    # The analysis reads its own copy. The same original can start more than one job.
    shutil.copyfile(path, dest)
    return dest


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
        jobqueue.submit(background, fetch_then, job["id"], link["url"], run_autocut, *args)
    else:
        jobqueue.submit(background, run_autocut, job["id"], adopt(staged, job["id"]), *args)
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
    only_me: str = Form(""),
    staged: str = Form(""),
    source_job: str = Form(""),
    source_rally: str = Form(""),
) -> dict:
    if stroke not in STROKES:
        raise validate.Invalid(f"Unknown stroke: {stroke}. Leave it blank to auto-detect.")
    if stroke_type and stroke_type not in STROKE_TYPES:
        raise validate.Invalid(f"Unknown stroke type: {stroke_type}. Pick one from the list, or leave it blank to auto-detect.")
    validate.choice(hand, "hand", "Bat hand")
    selection = validate.player_selection(player_time, player_box)
    solo = validate.only_me(only_me) and not selection   # a tapped player wins
    player = validate.text(player, "player", "The player's name")
    text = validate.text(text, "training_text", "The training description")
    staged, filename = uploaded_match(source_job, source_rally) if source_job else take_video(video, staged)
    link = check_link(url, "breakdown") if staged is None else None
    if staged is None and link is None and not text:
        raise validate.Invalid("Upload a clip, paste a YouTube link, or describe the training.")
    params = {"stroke": stroke, "stroke_type": stroke_type or "auto", "player": player, "text": text, "hand": hand,
              "video": filename if staged else (link["title"] if link else None),
              "url": link and link["url"]}
    if selection and (staged or link):
        params["player_pick"] = {"time": selection[0], "box": list(selection[1])}
    solo = solo and bool(staged or link)
    if solo:
        params["only_me"] = True
    if source_job:
        params["source_job"] = source_job
        if source_rally:
            params["source_rally"] = int(source_rally)
    job = jobs.create("breakdown", params)
    # The tapped player goes last, and only when there is one, so other calls are unchanged.
    args = (text, stroke, player, hand, stroke_type) + ((selection,) if selection and (staged or link) else ())
    kwargs = {"only_me": True} if solo else {}
    if link:
        jobqueue.submit(background, fetch_then, job["id"], link["url"], run_breakdown, *args, **kwargs)
    else:
        path = analysis_input(staged, job["id"], source_job) if staged else None
        jobqueue.submit(background, run_breakdown, job["id"], path, *args, **kwargs)
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
    staged: str = Form(""),
) -> dict:
    validate.choice(stroke, "match_stroke", "Stroke")
    selection = validate.player_selection(player_time, player_box)
    validate.choice(hand, "hand", "Bat hand")
    validate.choice(grip, "grip", "Grip")
    height = validate.height_cm(height_cm)
    staged, filename = take_video(video, staged)
    link = None if staged else check_link(url, "match")
    if not staged and link is None:
        raise validate.Invalid("Upload a clip of yourself or paste a YouTube link.")
    params = {"video": filename if staged else link["title"], "url": link and link["url"],
              "stroke": stroke, "hand": hand, "grip": grip, "height_cm": height}
    if selection:
        params["player_pick"] = {"time": selection[0], "box": list(selection[1])}
    job = jobs.create("match", params)
    args = (stroke, height, hand, grip) + ((selection,) if selection else ())
    if link:
        jobqueue.submit(background, fetch_then, job["id"], link["url"], run_match, *args)
    else:
        jobqueue.submit(background, run_match, job["id"], adopt(staged, job["id"]), *args)
    return job


@app.post("/jobs/coach", status_code=201)
def create_coach(
    background: BackgroundTasks,
    request: str = Form(""),
    video: UploadFile | None = File(None),
    url: str = Form(""),
    player_time: str = Form(""),
    player_box: str = Form(""),
    only_me: str = Form(""),
    staged: str = Form(""),
    source_job: str = Form(""),
    source_rally: str = Form(""),
) -> dict:
    """TT Coach: one request about one video, handled by the deep agent (agent/coach.py).
    Falls back to the classic pipelines when there is no API key or the agent fails."""
    from agent.coach import run_coach

    request = validate.text(request, "coach_request", "Your request")
    selection = validate.player_selection(player_time, player_box)
    solo = validate.only_me(only_me) and not selection   # a tapped player wins
    if not request:
        raise validate.Invalid("Tell the coach what you want, e.g. 'show my best rallies and fix my forehand'.")
    staged, filename = uploaded_match(source_job, source_rally) if source_job else take_video(video, staged)
    link = None if staged else check_link(url, "coach")
    if not staged and link is None:
        raise validate.Invalid("Add a video: upload a clip or paste a YouTube link.")
    params = {"request": request, "video": filename if staged else link["title"],
              "url": link and link["url"]}
    if selection:
        params["player_pick"] = {"time": selection[0], "box": list(selection[1])}
    if solo:
        params["only_me"] = True
    if source_job:
        params["source_job"] = source_job
        if source_rally:
            params["source_rally"] = int(source_rally)
    job = jobs.create("coach", params)
    path = analysis_input(staged, job["id"], source_job) if staged else None
    if path is not None and not jobqueue.inline():
        # Start the analysis the job will need now, beside any job ahead of it in the queue.
        from agent.fixed import prepare
        jobqueue.submit(background, prepare, job["id"], jobqueue.prepare_link(path), selection, solo,
                        lane="prepare", kind="prepare")
    jobqueue.submit(background, run_coach, job["id"], path, link and link["url"], request,
                        *((selection,) if selection else ()), **({"only_me": True} if solo else {}))
    return job


# Finding players runs here, off the event loop, so the API keeps answering and two pickers
# don't wait on each other (1.6-2.0 s each when run together). Two threads: each loads a model.
PLAYER_THREADS = 2
PLAYER_POOL = ThreadPoolExecutor(max_workers=PLAYER_THREADS, thread_name_prefix="players")


def warm_players() -> None:
    """Load the pose model on every detection thread at startup. Cold, the first picker paid
    ~2.7 s for imports and the model (measured 2026-11-18), on top of a 1.1 s Next.js compile."""
    barrier = threading.Barrier(PLAYER_THREADS)

    def load() -> None:
        try:
            from technique import people
            people.warm()
        except Exception as exc:   # detection still works, just slower the first time
            log.warning("players: warm-up failed: %s", exc)
        try:
            barrier.wait(timeout=30)   # hold this thread so the next task warms the other one
        except threading.BrokenBarrierError:
            pass

    for _ in range(PLAYER_THREADS):
        PLAYER_POOL.submit(load)


class ClientGone(Exception):
    """The browser closed the request (navigated away, changed video, or timed out)."""


async def run_while_connected(request: Request, fn, *args):
    """fn(*args, cancel=Event) in PLAYER_POOL; if the browser disconnects, set the event (fn stops
    at its next step) and raise ClientGone instead of finishing work nobody will read."""
    cancel = threading.Event()
    future = asyncio.get_running_loop().run_in_executor(PLAYER_POOL, partial(fn, *args, cancel=cancel))
    while True:
        done, _ = await asyncio.wait({future}, timeout=0.25)
        if done:
            return future.result()
        if await request.is_disconnected():
            cancel.set()
            future.add_done_callback(lambda f: f.exception())   # collect its Cancelled quietly
            raise ClientGone()


def _detect_frames(sent: list[tuple[float, bytes]], queued: float, cancel: threading.Event) -> dict:
    start = time.monotonic()
    import cv2
    import numpy as np

    from technique import people

    images = []
    for t, data in sent:
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise validate.Invalid("A frame couldn't be read as an image.")
        images.append((t, image))
    decoded = time.monotonic()
    result = people.detect(images, cancel=cancel)
    result.setdefault("timing", {}).update(wait_s=round(start - queued, 2), decode_s=round(decoded - start, 2))
    return result


def _stop_if(cancel: threading.Event) -> None:
    if cancel.is_set():
        from technique.people import Cancelled
        raise Cancelled()


def _detect_video(path: Path | None, url: str | None, queued: float, cancel: threading.Event) -> dict:
    """A stored upload, or a link downloaded just for finding the players and then deleted."""
    start = time.monotonic()
    from technique import people

    folder = None
    try:
        if path is None:
            folder = jobs.DATA_DIR / ".players" / uuid.uuid4().hex
            folder.mkdir(parents=True, exist_ok=True)
            # A page that leaves stops the download too (it used to hold a detection thread).
            path = download.download(url, folder, progress=lambda f: _stop_if(cancel))
        fetched = time.monotonic()
        _stop_if(cancel)
        frames = people.sample_frames(str(path))
        sampled = time.monotonic()
        result = people.detect(frames, cancel=cancel)
    finally:
        if folder is not None:
            shutil.rmtree(folder, ignore_errors=True)
    result.setdefault("timing", {}).update(wait_s=round(start - queued, 2), download_s=round(fetched - start, 2),
                            sample_s=round(sampled - fetched, 2))
    return result


def _detect_summary(source: str, r: dict) -> str:
    """One log line per lookup: what came in, who was found in each frame, where the time went."""
    t = r.get("timing", {})
    phases = " + ".join(f"{k[:-2]} {t[k]:.2f}" for k in ("probe_s", "read_s", "stage_s", "wait_s", "download_s",
                                                          "sample_s", "decode_s") if k in t)
    per_frame = " ".join(f"{f['time']:.1f}s:{f['people']}" for f in r.get("frames", []))
    return (f"players/detect {source}: {t.get('frames', 0)} frames [{per_frame}] -> "
            f"{len(r.get('candidates', []))} players; {t.get('total_s', 0):.2f} s = {phases} + "
            f"detect {t.get('seconds', 0):.2f} (model {t.get('model_load_s', 0):.2f}, zoomed {t.get('zoomed_frames', 0)})")


@app.post("/players/detect")
async def detect_players(
    request: Request,
    frames: list[UploadFile] | None = File(None),
    times: str = Form(""),
    url: str = Form(""),
    kind: str = Form("breakdown"),
    job: str = Form(""),
    video: UploadFile | None = File(None),
):
    """The players in frames of the chosen video, for "Which one is you?". The browser sends
    frames it drew from the file (no upload of the video). When it can't read the file (Chrome
    without an HEVC decoder and an iPhone .MOV), it sends the video: we read the frames with
    ffmpeg and keep the upload for the job (`staged`). For a pasted link we download it."""
    from technique.people import Cancelled

    if kind not in ("breakdown", "match", "coach"):
        raise validate.Invalid("kind must be breakdown, match or coach.")
    t0 = time.monotonic()
    extra: dict = {}
    try:
        if job:
            # "Change player" on a result: the job's stored upload, or its link downloaded again.
            stored = job_input(job)
            link_url = None if stored else (jobs.load(job) or {}).get("params", {}).get("url")
            if stored is None and not link_url:
                raise validate.Invalid("This job's video is no longer here. Upload it again to pick a player.")
            source = "job video" if stored else "job link"
            result = await run_while_connected(request, _detect_video, stored, link_url, time.monotonic())
        elif has_file(video):
            # Saving and checking a phone video (ffprobe) blocks: off the event loop.
            path = await run_in_threadpool(stage_upload, video)
            extra["stage_s"] = round(time.monotonic() - t0, 2)
            source = f"uploaded video ({path.stat().st_size // 1_000_000} MB)"
            result = await run_while_connected(request, _detect_video, path, None, time.monotonic())
            result["staged"] = keep_for_job(path, video.filename)
            if not jobqueue.inline():
                # The video is on the server now: start its rallies and play check (who isn't
                # known until the user taps), so a Coach job on it starts ahead.
                from agent.fixed import prepare
                jobqueue.submit(BackgroundTasks(), prepare, "players", jobqueue.prepare_link(path), None, False,
                                False, lane="prepare", kind="prepare")
        else:
            sent = [(f.filename, await f.read()) for f in (frames or []) if has_file(f)]
            extra["read_s"] = round(time.monotonic() - t0, 2)
            if sent or not url.strip():
                source = f"browser frames ({sum(len(d) for _, d in sent) // 1024} KB)"
                result = await run_while_connected(request, _detect_frames, validate.player_frames(sent, times),
                                                   time.monotonic())
            else:
                # yt-dlp's probe is a blocking network call (~10 s): off the event loop, or every
                # other request (job polling, other pickers) waits for it.
                link = await run_in_threadpool(check_link, url, kind)
                extra["probe_s"] = round(time.monotonic() - t0 - extra["read_s"], 2)
                source = "link"
                result = await run_while_connected(request, _detect_video, None, link["url"], time.monotonic())
    except (ClientGone, Cancelled):
        log.info("players/detect: the browser left after %.2f s; stopped", time.monotonic() - t0)
        return Response(status_code=499)   # nginx's "client closed request"; nobody reads it
    result.setdefault("timing", {}).update(extra, total_s=round(time.monotonic() - t0, 2))
    log.info(_detect_summary(source, result))
    return result


def job_input(job_id: str) -> Path | None:
    """A job's stored upload (input.<ext>), if it still exists. Links are deleted after the job."""
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise validate.Invalid("Unknown job.")
    return next(iter(sorted(jobs.job_dir(job_id).glob("input.*"))), None)


@app.post("/jobs/{job_id}/rerun", status_code=201)
def rerun_job(job_id: str, background: BackgroundTasks, player_time: str = Form(""),
              player_box: str = Form("")) -> dict:
    """'Change player': the same job again on the same video, following a different player."""
    from agent.coach import run_coach

    selection = validate.player_selection(player_time, player_box)
    if selection is None:
        raise validate.Invalid(validate.PICK_AGAIN)
    stored = job_input(job_id)
    old = jobs.load(job_id)
    if not old or old.get("kind") not in ("breakdown", "match", "coach"):
        raise validate.Invalid("Only Breakdown, Pro match and Coach results can change player.")
    p = old["params"]
    url = None if stored else p.get("url")
    if stored is None and not url:
        raise validate.Invalid("This job's video is no longer here. Upload it again to pick a player.")
    params = {**p, "player_pick": {"time": selection[0], "box": list(selection[1])}, "rerun_of": job_id}
    job = jobs.create(old["kind"], params)
    path = None
    if stored is not None:
        path = jobs.job_dir(job["id"]) / stored.name
        shutil.copyfile(stored, path)
    if old["kind"] == "breakdown":
        fn, args = run_breakdown, (p.get("text") or "", p.get("stroke") or "", p.get("player") or "",
                                   p.get("hand") or "auto",
                                   "" if p.get("stroke_type") in (None, "auto") else p["stroke_type"], selection)
    elif old["kind"] == "match":
        fn, args = run_match, (p.get("stroke") or "forehand", p.get("height_cm"), p.get("hand") or "auto",
                               p.get("grip") or "shakehand", selection)
    else:
        jobqueue.submit(background, run_coach, job["id"], path, url, p.get("request") or "", selection)
        return job
    if url:
        jobqueue.submit(background, fetch_then, job["id"], url, fn, *args)
    else:
        jobqueue.submit(background, fn, job["id"], path, *args)
    return job


@app.post("/jobs/{job_id}/exports")
def export_highlights(job_id: str, rallies: list[StrictInt] = Body(embed=True)) -> dict:
    """Export the supplied rally IDs in order, keeping the original reel available."""
    job = jobs.load(job_id) if re.fullmatch(r"[0-9a-f]{32}", job_id) else None
    if not job or job["kind"] != "autocut" or job["status"] != "done":
        raise HTTPException(404, "Open a finished match result to export highlights.")
    available = {rally["id"] for rally in job.get("rallyClips", [])}
    if not rallies or len(set(rallies)) != len(rallies) or not set(rallies) <= available:
        raise validate.Invalid("Choose at least one available rally, once each.")

    folder = jobs.job_dir(job_id)
    parts = [folder / f"rally-{rally}.mp4" for rally in rallies]
    if not all(part.is_file() for part in parts):
        raise validate.Invalid("Some rally clips are no longer available. Upload the match again.")
    tag = hashlib.sha256(",".join(map(str, rallies)).encode()).hexdigest()[:20]
    dest = folder / f"highlights-{tag}.mp4"
    if not dest.exists():
        try:
            with TemporaryDirectory(dir=folder) as work:
                temp = Path(work) / "highlights.mp4"
                concat_parts(parts, temp)
                temp.replace(dest)
        except (OSError, subprocess.CalledProcessError):
            log.exception("Highlight export failed for %s", job_id)
            raise HTTPException(500, "Couldn't make this download. Try again.") from None
    return {"url": f"/jobs/{job_id}/files/{dest.name}"}


@app.get("/jobs/{job_id}/files/{name}")
def get_file(job_id: str, name: str) -> FileResponse:
    """A result video or a rally thumbnail."""
    picture = bool(re.fullmatch(r"rally-[1-9][0-9]*\.jpg", name))
    if not (picture or re.fullmatch(r"[\w-]{1,64}\.mp4", name)) or not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise HTTPException(404, "not found")
    path = jobs.job_dir(job_id) / name
    if not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path, media_type="image/jpeg" if picture else "video/mp4",
                        filename=None if picture else f"ttskill-{name}")


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job["kind"] == "autocut" and job["status"] == "done" and re.fullmatch(r"[0-9a-f]{32}", job_id):
        job["canReuseVideo"] = job_input(job_id) is not None
    return job


@app.get("/jobs/{job_id}/result")
def get_result(job_id: str) -> FileResponse:
    path = jobs.job_dir(job_id) / "result.mp4"
    if not path.exists():
        raise HTTPException(404, "no result yet")
    return FileResponse(path, media_type="video/mp4", filename=f"ttskill-{job_id}.mp4")
