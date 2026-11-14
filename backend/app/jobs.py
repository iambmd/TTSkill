"""Job records stored on local disk under data/jobs/<id>/job.json."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "jobs"


def job_dir(job_id: str) -> Path:
    return DATA_DIR / job_id


def create(kind: str, params: dict[str, Any]) -> dict[str, Any]:
    job = {"id": uuid.uuid4().hex, "kind": kind, "status": "queued", "progress": 0.0,
           "message": None, "params": params, "resultUrl": None}
    job_dir(job["id"]).mkdir(parents=True, exist_ok=True)
    save(job)
    return job


def save(job: dict[str, Any]) -> None:
    (job_dir(job["id"]) / "job.json").write_text(json.dumps(job, indent=2))


def load(job_id: str) -> dict[str, Any] | None:
    path = job_dir(job_id) / "job.json"
    return json.loads(path.read_text()) if path.exists() else None


def update(job_id: str, **fields: Any) -> dict[str, Any]:
    job = load(job_id) or {}
    job.update(fields)
    save(job)
    return job
