"""The job queue and the worker (app/jobqueue.py, app/worker.py): jobs run outside the API,
each in its own process, with a time limit, and survive API reloads."""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

from app import cache, jobqueue, jobs, worker

sys.path.insert(0, str(Path(__file__).parent))   # so spawned job processes find worker_tasks
import worker_tasks  # noqa: E402


@pytest.fixture
def queued(tmp_path, monkeypatch):
    """Queue mode (no TTSKILL_INLINE) on a temporary data folder."""
    monkeypatch.delenv("TTSKILL_INLINE", raising=False)
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path / "jobs")
    monkeypatch.setattr(jobs, "ACTIVE", set())
    # Spawned job processes import app.jobs afresh: point them at the same folder.
    monkeypatch.setenv("TTSKILL_DATA_DIR", str(tmp_path / "jobs"))
    return tmp_path


def test_a_queued_job_runs_in_its_own_process(queued):
    job = jobs.create("coach", {})
    jobqueue.submit(None, worker_tasks.finish, job["id"], "made it")
    assert jobs.get(job["id"])["status"] == "queued"   # waits for the worker; not "orphaned"
    worker.main(once=True)
    done = jobs.load(job["id"])
    assert done["status"] == "done" and done["message"] == "made it" and done["pid"] != os.getpid()
    assert jobqueue.task_state(job["id"]) == "done"


def test_a_job_that_runs_too_long_is_stopped(queued, monkeypatch):
    monkeypatch.setitem(jobqueue.TIMEOUT_MIN, "coach", 0.03)   # ~2 s
    job = jobs.create("coach", {})
    jobqueue.submit(None, worker_tasks.sleep_forever, job["id"])
    started = time.time()
    worker.main(once=True)
    done = jobs.load(job["id"])
    assert done["status"] == "failed" and "longer than" in done["message"] and time.time() - started < 20
    assert jobqueue.task_state(job["id"]) == "timeout"


def test_a_job_process_that_dies_fails_its_job(queued):
    job = jobs.create("coach", {})
    jobqueue.submit(None, worker_tasks.crash, job["id"])
    worker.main(once=True)
    assert jobs.load(job["id"])["status"] == "failed" and jobqueue.task_state(job["id"]) == "failed"


def test_without_a_worker_a_queued_job_says_so_and_waits(queued):
    job = jobs.create("coach", {})
    jobqueue.submit(None, worker_tasks.finish, job["id"], "later")
    j = jobs.get(job["id"])
    assert j["status"] == "queued" and "Waiting for the worker" in j["message"]
    worker.main(once=True)   # the worker comes up later and still runs it
    assert jobs.load(job["id"])["status"] == "done"


def test_a_task_left_running_by_a_dead_worker_fails_on_restart(queued):
    job = jobs.create("coach", {})
    jobqueue.submit(None, worker_tasks.finish, job["id"], "never")
    with jobqueue.connect() as con:
        jobqueue.claim(con, "jobs")   # claimed, then the worker died
    jobs.update(job["id"], status="running")
    assert jobs.get(job["id"])["status"] == "failed"   # no live worker: the page stops waiting
    job2 = jobs.create("coach", {})
    jobqueue.submit(None, worker_tasks.finish, job2["id"], "never")
    with jobqueue.connect() as con:
        jobqueue.claim(con, "jobs")
        jobs.update(job2["id"], status="running")
        worker.recover(con)
    assert jobs.load(job2["id"])["status"] == "failed" and "restarted" in jobs.load(job2["id"])["message"]


def test_inline_mode_runs_jobs_in_the_api_as_before(tmp_path, monkeypatch):
    monkeypatch.setenv("TTSKILL_INLINE", "1")
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path / "jobs")
    added = []
    background = type("B", (), {"add_task": lambda self, *a, **k: added.append(a)})()
    jobqueue.submit(background, worker_tasks.finish, "x", "y")
    jobqueue.submit(background, worker_tasks.finish, "x", "y", lane="prepare")   # a head start: skipped inline
    assert added == [(jobs.run, worker_tasks.finish, "x", "y")]


def test_one_computer_per_cache_entry(tmp_path, monkeypatch):
    """A job that needs an entry the prepare task is computing waits for it, not redoes it."""
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path / "jobs")
    calls = []

    def slow():
        calls.append(1)
        time.sleep(0.3)
        return "rallies"
    results = []
    threads = [threading.Thread(target=lambda: results.append(cache.cached("k", "rallies", slow))) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert calls == [1] and sorted(hit for _, hit in results) == [False, True, True]


def test_prepare_fills_the_cache_a_coach_job_reads(tmp_path, monkeypatch):
    from agent import fixed
    from app.rally import Rally
    from technique import hitpose
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path / "jobs")
    video = tmp_path / "v.mp4"
    video.write_bytes(b"a video")
    link = jobqueue.prepare_link(video)
    monkeypatch.setattr(fixed, "heard", lambda v, w: ([Rally(1.0, 4.0, 6, times=__import__("numpy").array([2.0]))], 4))
    monkeypatch.setattr(fixed, "find_seed", lambda v, sel, only: "seed")
    monkeypatch.setattr(hitpose, "hit_pose", lambda *a: "strokes")
    monkeypatch.setattr(fixed, "play_checked", lambda v, raw, m: ["kept"])
    fixed.prepare("job", str(link))
    key = cache.video_key(video)
    names = sorted(p.name.split(".")[0] for p in (cache.root() / key).glob("*.pkl"))
    assert names == ["audio_rallies", "hitpose-auto", "rallies", "seed-auto"]
    assert not link.exists() and video.exists()   # the hard link is gone, the upload stays
