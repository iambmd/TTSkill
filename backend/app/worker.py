"""`python -m app.worker`: runs the queued jobs (app/jobqueue.py), each in a fresh process
with a time limit, and the prepare tasks beside them.

A fresh (spawned) process per job means the job runs the current code (no restart after an
edit, unlike the API's --reload) and its memory is returned when it ends. This process stays
small: it imports no MediaPipe or OpenCV itself."""
from __future__ import annotations

import multiprocessing as mp
import os
import pickle
import signal
import socket
import threading
import time
import traceback
from contextlib import closing

from . import jobqueue, jobs

RESTARTED = "The worker restarted before this job finished. Please try again."


def _child(payload: bytes, lane: str) -> None:
    fn, job_id, args, kwargs = pickle.loads(payload)
    if lane == "prepare":   # a head start for a job: never touches the job's record
        fn(job_id, *args, **kwargs)
    else:
        jobs.run(fn, job_id, *args, **kwargs)


def _beat(name: str, stop: threading.Event) -> None:
    with closing(jobqueue.connect()) as con:
        while not stop.is_set():
            con.execute("INSERT OR REPLACE INTO workers (name, pid, beat) VALUES (?,?,?)", (name, os.getpid(), time.time()))
            stop.wait(jobqueue.HEARTBEAT_S)


def recover(con) -> None:
    """Tasks left running by a worker that died: their jobs fail with a message to retry."""
    for task_id, job_id, lane in con.execute("SELECT id, job_id, lane FROM tasks WHERE status='running'").fetchall():
        jobqueue.finish(con, task_id, "failed", "worker restarted")
        job = jobs.load(job_id)
        if lane == "jobs" and job and job.get("status") in ("queued", "running"):
            jobs.update(job_id, status="failed", message=RESTARTED)


def main(slots: int | None = None, once: bool = False) -> None:
    """Run tasks until stopped (once: until the queue is empty, for tests)."""
    slots = slots or int(os.environ.get("TTSKILL_WORKERS", "1"))
    lanes = {"jobs": slots, "prepare": 1}
    ctx = mp.get_context("spawn")
    name = f"{socket.gethostname()}:{os.getpid()}"
    stop = threading.Event()
    threading.Thread(target=_beat, args=(name, stop), daemon=True).start()
    running: dict[int, tuple] = {}   # task id -> (process, job id, kind, lane, started)
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    print(f"worker {name}: {slots} job slot(s) + 1 prepare slot", flush=True)
    with closing(jobqueue.connect()) as con:
        recover(con)
        try:
            while not stop.is_set():
                for lane, cap in lanes.items():
                    while sum(1 for r in running.values() if r[3] == lane) < cap:
                        row = jobqueue.claim(con, lane)
                        if row is None:
                            break
                        task_id, job_id, kind, payload = row
                        proc = ctx.Process(target=_child, args=(payload, lane), name=f"{kind}-{job_id[:8]}")
                        proc.start()
                        con.execute("UPDATE tasks SET pid=? WHERE id=?", (proc.pid, task_id))
                        running[task_id] = (proc, job_id, kind, lane, time.time())
                        print(f"start {kind} {job_id} (pid {proc.pid})", flush=True)
                for task_id, (proc, job_id, kind, lane, started) in list(running.items()):
                    limit = jobqueue.TIMEOUT_MIN.get(kind, 15) * 60
                    if proc.is_alive() and time.time() - started > limit:
                        proc.kill()
                        proc.join(5)
                        jobqueue.finish(con, task_id, "timeout")
                        if lane == "jobs":
                            jobs.update(job_id, status="failed", message=jobqueue.timeout_message(kind))
                        print(f"timeout {kind} {job_id} after {limit // 60} min", flush=True)
                        del running[task_id]
                    elif not proc.is_alive():
                        proc.join()
                        ok = proc.exitcode == 0
                        jobqueue.finish(con, task_id, "done" if ok else "failed", None if ok else f"exit {proc.exitcode}")
                        job = jobs.load(job_id) if lane == "jobs" else None
                        if job and job.get("status") in ("queued", "running"):   # killed (OOM, signal)
                            jobs.update(job_id, status="failed", message=jobs.UNFINISHED)
                        print(f"end {kind} {job_id}: exit {proc.exitcode} in {time.time() - started:.0f} s", flush=True)
                        del running[task_id]
                if once and not running and not con.execute("SELECT 1 FROM tasks WHERE status='queued'").fetchone():
                    break
                stop.wait(0.3)
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            for task_id, (proc, job_id, kind, lane, _) in running.items():
                proc.terminate()
                proc.join(5)
                jobqueue.finish(con, task_id, "failed", "worker stopped")
                if lane == "jobs":
                    jobs.update(job_id, status="failed", message=RESTARTED)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
