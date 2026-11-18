"""Per-video cache of the slow analysis steps (rallies, player seed, pose at the hits and on
the coached stroke's clip), keyed by the video's content hash, so the same video again
("Change player", another request, a re-upload) skips them. Lives in backend/data/cache/<hash>/;
safe to delete at any time."""
from __future__ import annotations

import hashlib
import pickle
from pathlib import Path
from typing import Any, Callable

from . import jobs

VERSION = 1   # bump when a cached step's output changes shape or meaning


def root() -> Path:
    return jobs.DATA_DIR.parent / "cache"


def video_key(path: str | Path) -> str:
    """SHA-256 of the file's bytes (~0.4 s for a 240 MB phone video)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:32]


def cached(video_key_: str, name: str, compute: Callable[[], Any]) -> tuple[Any, bool]:
    """compute()'s result, from the cache when this video already has it. Returns (value, hit).
    Pickle, because the values are our own numpy/dataclass objects written by this app.
    One computer per entry: a job that needs an entry the worker's prepare task is computing
    waits for it instead of doing the same work (file lock, across processes)."""
    import fcntl

    path = root() / video_key_ / f"{name}.v{VERSION}.pkl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            try:
                return pickle.loads(path.read_bytes()), True
            except Exception:   # a half-written or stale entry: compute it again
                path.unlink(missing_ok=True)
        value = compute()
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(pickle.dumps(value))
        tmp.replace(path)
        return value, False
