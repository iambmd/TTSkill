"""The job queue: the API puts jobs in a SQLite table and `python -m app.worker` runs them, each
in its own process with a time limit. Jobs no longer live in the API process, so an API reload
(`make backend --reload` on a file save) doesn't kill them, and a stuck job is stopped.

Redis (for RQ) isn't installed on the dev machine and can't be without sudo; one SQLite file
does the same job for one machine, with nothing new to install.

Two lanes: "jobs" (TTSKILL_WORKERS at a time, default 1: a job takes ~3 GB) and "prepare"
(one at a time): the analysis a job will need, started as soon as its video is on disk.
TTSKILL_INLINE=1 runs jobs inside the API as before (the tests, or a machine without a worker)."""
from __future__ import annotations

import os
import pickle
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Callable

from messages import Msg
from . import jobs

# Minutes before a job is stopped. Phase 1 Coach jobs take 1.5-2 min, a 60-minute Auto-Cut
# much longer; these are hangs, not budgets.
TIMEOUT_MIN = {"autocut": 30, "breakdown": 15, "match": 15, "coach": 15, "prepare": 10}
HEARTBEAT_S = 2.0
STALE_S = 15.0       # a worker silent this long is gone
WAITING = str(Msg("progress.waiting"))


def db_path() -> Path:
    return jobs.DATA_DIR.parent / "queue.sqlite3"


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(db_path(), timeout=30, isolation_level=None)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY, job_id TEXT, kind TEXT, lane TEXT, payload BLOB, status TEXT,
        pid INTEGER, created REAL, started REAL, finished REAL, error TEXT)""")
    con.execute("CREATE TABLE IF NOT EXISTS workers (name TEXT PRIMARY KEY, pid INTEGER, beat REAL)")
    return con


def inline() -> bool:
    return os.environ.get("TTSKILL_INLINE") == "1"


def submit(background, fn: Callable[..., None], job_id: str, *args: Any, kind: str | None = None,
           lane: str = "jobs", **kwargs: Any) -> None:
    """Queue fn(job_id, *args, **kwargs) for the worker. Inline: FastAPI's background task,
    as before. fn and the arguments are pickled (module-level functions, paths, tuples)."""
    if inline():
        if lane == "jobs":   # prepare is only a head start; inline jobs do the work themselves
            background.add_task(jobs.run, fn, job_id, *args, **kwargs)
        return
    if kind is None:
        kind = (jobs.load(job_id) or {}).get("kind", "jobs")
    payload = pickle.dumps((fn, job_id, args, kwargs))
    with closing(connect()) as con:
        con.execute("INSERT INTO tasks (job_id, kind, lane, payload, status, created) VALUES (?,?,?,?,?,?)",
                    (job_id, kind, lane, payload, "queued", time.time()))


def worker_alive(con: sqlite3.Connection | None = None) -> bool:
    own = con is None
    con = con or connect()
    try:
        row = con.execute("SELECT MAX(beat) FROM workers").fetchone()
        return bool(row and row[0] and time.time() - row[0] < STALE_S)
    finally:
        if own:
            con.close()


def task_state(job_id: str) -> str | None:
    """The job's queue status (queued/running/done/failed/timeout), or None if not queued here."""
    if not db_path().exists():
        return None
    with closing(connect()) as con:
        row = con.execute("SELECT status FROM tasks WHERE job_id=? AND lane='jobs' ORDER BY id DESC LIMIT 1",
                          (job_id,)).fetchone()
    return row[0] if row else None


def claim(con: sqlite3.Connection, lane: str) -> tuple[int, str, str, bytes] | None:
    """Take the oldest queued task of a lane (atomically: one worker gets it)."""
    con.execute("BEGIN IMMEDIATE")
    try:
        row = con.execute("SELECT id, job_id, kind, payload FROM tasks WHERE status='queued' AND lane=? "
                          "ORDER BY id LIMIT 1", (lane,)).fetchone()
        if row:
            con.execute("UPDATE tasks SET status='running', started=? WHERE id=?", (time.time(), row[0]))
        con.execute("COMMIT")
        return row
    except Exception:
        con.execute("ROLLBACK")
        raise


def finish(con: sqlite3.Connection, task_id: int, status: str, error: str | None = None) -> None:
    con.execute("UPDATE tasks SET status=?, finished=?, error=? WHERE id=?", (status, time.time(), error, task_id))


def timeout_message(kind: str) -> Msg:
    return Msg("progress.timeout", minutes=TIMEOUT_MIN.get(kind, 15))


def prepare_link(path: Path) -> Path:
    """A hard link to an upload for a prepare task: the job moves the upload into its folder
    (adopt) while prepare may still be reading it. Same filesystem, so it costs nothing."""
    import shutil
    import uuid

    d = jobs.DATA_DIR / ".prepare"
    d.mkdir(parents=True, exist_ok=True)
    link = d / f"{uuid.uuid4().hex}{path.suffix}"
    try:
        os.link(path, link)
    except OSError:
        shutil.copyfile(path, link)
    return link
