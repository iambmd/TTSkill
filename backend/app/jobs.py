"""Job records stored on local disk under data/jobs/<id>/job.json."""
from __future__ import annotations

import json
import os
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable

# TTSKILL_DATA_DIR moves it (the worker's job processes read it too, so tests can point both
# the test and the spawned jobs at a temporary folder).
DATA_DIR = Path(os.environ.get("TTSKILL_DATA_DIR") or Path(__file__).resolve().parents[1] / "data" / "jobs")

# Jobs this process is working on (inline mode, TTSKILL_INLINE=1, and scripts). A record that
# says queued/running but is neither in here nor queued for the worker (app/jobqueue.py) was
# orphaned: whatever ran it died, so nothing will ever finish it.
ACTIVE: set[str] = set()
RESTARTED = "The server restarted before this job finished. Please try again."
UNFINISHED = "The job stopped without finishing. Please try again."
FAILED = "We couldn't finish this analysis. Try again or upload a shorter clip."
_LOCK = threading.RLock()  # serialise read-modify-write of job.json within the process


def job_dir(job_id: str) -> Path:
    return DATA_DIR / job_id


def create(kind: str, params: dict[str, Any]) -> dict[str, Any]:
    job = {"id": uuid.uuid4().hex, "kind": kind, "status": "queued", "progress": 0.0,
           "message": None, "params": params, "resultUrl": None}
    job_dir(job["id"]).mkdir(parents=True, exist_ok=True)
    from .jobqueue import inline
    if inline():   # run in this process: live from the start, so an early poll isn't "orphaned"
        ACTIVE.add(job["id"])
    save(job)
    return job


def save(job: dict[str, Any]) -> None:
    # Write then rename, so a poll never reads a half-written file. The API and the worker
    # both write, so the temp name carries the process id too.
    path = job_dir(job["id"]) / "job.json"
    tmp = path.with_name(f"job.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(job, indent=2))
    os.replace(tmp, path)


def load(job_id: str) -> dict[str, Any] | None:
    path = job_dir(job_id) / "job.json"
    return json.loads(path.read_text()) if path.exists() else None


def update(job_id: str, **fields: Any) -> dict[str, Any]:
    import fcntl

    with _LOCK:
        d = job_dir(job_id)
        d.mkdir(parents=True, exist_ok=True)
        # Read-modify-write under a file lock: the worker's job process and the API (and the
        # job's own threads) update the same record.
        with open(d / ".lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            job = load(job_id) or {}
            job.update(fields)
            save(job)
            return job


def get(job_id: str) -> dict[str, Any] | None:
    """The job for API readers: an orphaned queued/running job is marked failed, so the page
    shows an error instead of polling forever. Jobs run by the worker (app/jobqueue.py) are
    checked against the queue: a queued job waits (and says so if no worker is running); one
    whose task ended or whose worker died is failed."""
    from . import jobqueue

    with _LOCK:
        job = load(job_id)
        if not job or job.get("status") not in ("queued", "running"):
            return job
        state = None if job_id in ACTIVE else jobqueue.task_state(job_id)
        if job_id in ACTIVE:
            return job
        if state == "queued":
            if not jobqueue.worker_alive() and job.get("message") != jobqueue.WAITING:
                job = update(job_id, message=jobqueue.WAITING)
        elif state == "running":
            if not jobqueue.worker_alive():
                job = update(job_id, status="failed", message=RESTARTED, failureHint=RESTARTED)
        elif state in ("done", "failed", "timeout"):
            job = update(job_id, status="failed", message=UNFINISHED, failureHint=UNFINISHED)
        else:
            job = update(job_id, status="failed", message=RESTARTED, failureHint=RESTARTED)
        return job


def fail(job_id: str, exc: Exception, fallback: str = FAILED) -> None:
    """Use friendly, deliberately authored errors and keep unexpected details in server logs."""
    from technique.errors import NoPlayer
    from .download import LinkError
    from .validate import Invalid

    hint = str(exc) if isinstance(exc, (NoPlayer, LinkError, Invalid)) else fallback
    update(job_id, status="failed", message=hint, failureHint=hint)


def run(fn: Callable[..., None], job_id: str, *args: Any, **kwargs: Any) -> None:
    """Run a pipeline as a background task. Whatever happens inside, the job ends done or
    failed: an uncaught error, or a pipeline that returns without a final status, fails it."""
    ACTIVE.add(job_id)
    try:
        fn(job_id, *args, **kwargs)
    except Exception as exc:
        traceback.print_exc()
        fail(job_id, exc)
    finally:
        ACTIVE.discard(job_id)
        job = load(job_id)
        if job and job.get("status") in ("queued", "running"):
            update(job_id, status="failed", message=UNFINISHED, failureHint=UNFINISHED)
