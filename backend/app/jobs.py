"""Job records stored on local disk under data/jobs/<id>/job.json."""
from __future__ import annotations

import json
import os
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "jobs"

# Jobs this process is working on. A record that says queued/running but is not in here was
# orphaned: its worker died with an earlier process (uvicorn --reload on a file save, a
# crash, Ctrl-C), so nothing will ever finish it. Assumes one worker process.
ACTIVE: set[str] = set()
RESTARTED = "The server restarted before this job finished. Please try again."
UNFINISHED = "The job stopped without finishing. Please try again."
_LOCK = threading.RLock()  # serialise read-modify-write of job.json within the process


def job_dir(job_id: str) -> Path:
    return DATA_DIR / job_id


def create(kind: str, params: dict[str, Any]) -> dict[str, Any]:
    job = {"id": uuid.uuid4().hex, "kind": kind, "status": "queued", "progress": 0.0,
           "message": None, "params": params, "resultUrl": None}
    job_dir(job["id"]).mkdir(parents=True, exist_ok=True)
    ACTIVE.add(job["id"])  # live from the start, so a poll before the task starts isn't "orphaned"
    save(job)
    return job


def save(job: dict[str, Any]) -> None:
    # Write then rename, so a poll never reads a half-written file.
    path = job_dir(job["id"]) / "job.json"
    tmp = path.with_name(f"job.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(job, indent=2))
    os.replace(tmp, path)


def load(job_id: str) -> dict[str, Any] | None:
    path = job_dir(job_id) / "job.json"
    return json.loads(path.read_text()) if path.exists() else None


def update(job_id: str, **fields: Any) -> dict[str, Any]:
    with _LOCK:
        job = load(job_id) or {}
        job.update(fields)
        save(job)
        return job


def get(job_id: str) -> dict[str, Any] | None:
    """The job for API readers: an orphaned queued/running job is marked failed, so the page
    shows an error instead of polling forever."""
    with _LOCK:
        job = load(job_id)
        if job and job.get("status") in ("queued", "running") and job_id not in ACTIVE:
            job = update(job_id, status="failed", message=RESTARTED)
        return job


def run(fn: Callable[..., None], job_id: str, *args: Any) -> None:
    """Run a pipeline as a background task. Whatever happens inside, the job ends done or
    failed: an uncaught error, or a pipeline that returns without a final status, fails it."""
    ACTIVE.add(job_id)
    try:
        fn(job_id, *args)
    except Exception as exc:
        traceback.print_exc()
        update(job_id, status="failed", message=str(exc) or type(exc).__name__)
    finally:
        ACTIVE.discard(job_id)
        job = load(job_id)
        if job and job.get("status") in ("queued", "running"):
            update(job_id, status="failed", message=UNFINISHED)
