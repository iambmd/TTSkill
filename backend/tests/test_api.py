"""Every API endpoint: input validation, what gets scheduled, job records, result and file
serving, and that a job can never stay queued/running forever (the "breakdown just sits
there" bug). Pipelines are replaced by recorders except in the end-to-end tests at the end."""
import os
import threading

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import download, jobs, main

VIDEO = {"video": ("clip.mp4", b"fake video bytes", "video/mp4")}
SHORT = "https://youtube.com/shorts/g3n9jVP0fMU"
CANONICAL = "https://www.youtube.com/watch?v=g3n9jVP0fMU"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs, "ACTIVE", set())
    return TestClient(main.app)


@pytest.fixture
def ran(monkeypatch):
    """Swap every pipeline for a recorder that finishes the job. Returns {name: [args, ...]}."""
    calls: dict[str, list] = {}

    def recorder(name):
        def run(job_id, *args):
            calls.setdefault(name, []).append(args)
            jobs.update(job_id, status="done", progress=1.0)
        return run

    for name in ("run_autocut", "run_breakdown", "run_match", "fetch_then"):
        monkeypatch.setattr(main, name, recorder(name))
    import agent.coach
    monkeypatch.setattr(agent.coach, "run_coach", recorder("run_coach"))
    return calls


@pytest.fixture
def link_ok(monkeypatch):
    monkeypatch.setattr(download, "probe", lambda url: {"id": "g3n9jVP0fMU", "title": "Ma Long forehand",
                                                        "duration": 32, "url": download.canonical(url)})


def _error(r) -> str:
    return r.json()["detail"]


# ------------------------------------------------------------------ health

def test_health(api):
    assert api.get("/health").json() == {"ok": True}


# ------------------------------------------------------------------ POST /jobs/autocut

def test_autocut_needs_a_video_or_link(api, ran):
    r = api.post("/jobs/autocut", data={"mode": "highlights"})
    assert r.status_code == 400 and "Upload a match video or paste a YouTube link" in _error(r)
    assert not ran


def test_autocut_rejects_unknown_mode(api, ran):
    r = api.post("/jobs/autocut", data={"mode": "best"}, files=VIDEO)
    assert r.status_code == 400 and "mode" in _error(r)


def test_autocut_rejects_links_that_are_not_youtube(api, ran):
    r = api.post("/jobs/autocut", data={"url": "https://vimeo.com/123"})
    assert r.status_code == 400 and "isn't a YouTube link" in _error(r)


def test_autocut_private_video_fails_on_the_form(api, ran, monkeypatch):
    def private(url):
        raise download.LinkError("That video is private. Use a public or unlisted video.")
    monkeypatch.setattr(download, "probe", private)
    r = api.post("/jobs/autocut", data={"url": SHORT})
    assert r.status_code == 400 and "private" in _error(r)
    assert not ran


def test_autocut_upload_saves_the_file_and_runs_the_pipeline(api, ran, tmp_path):
    r = api.post("/jobs/autocut", data={"mode": "full", "top_n": "3", "threshold": "2.5"}, files=VIDEO)
    assert r.status_code == 201
    job = r.json()
    assert job["kind"] == "autocut" and job["status"] == "queued" and job["params"]["mode"] == "full"
    path, *rest = ran["run_autocut"][0]
    assert path == tmp_path / job["id"] / "input.mp4" and path.read_bytes() == b"fake video bytes"
    assert rest == ["full", 3, 2.5, 1.6, 4]
    assert api.get(f"/jobs/{job['id']}").json()["status"] == "done"


def test_autocut_link_is_downloaded_first(api, ran, link_ok):
    r = api.post("/jobs/autocut", data={"url": SHORT, "mode": "highlights"})
    assert r.status_code == 201 and r.json()["params"]["url"] == CANONICAL
    url, pipeline, *rest = ran["fetch_then"][0]
    assert url == CANONICAL and pipeline is main.run_autocut and rest[0] == "highlights"


# ------------------------------------------------------------------ POST /jobs/breakdown

@pytest.mark.parametrize("data,expect", [
    ({"text": "loops", "stroke": "smash"}, "unknown stroke"),
    ({"text": "loops", "stroke_type": "tomahawk"}, "unknown stroke type"),
    ({"text": "loops", "hand": "both"}, "hand must be"),
    ({}, "Upload a clip, paste a YouTube link, or describe the training"),
    ({"text": "   "}, "Upload a clip"),
])
def test_breakdown_validation(api, ran, data, expect):
    r = api.post("/jobs/breakdown", data=data)
    assert r.status_code == 400 and expect in _error(r)
    assert not ran


def test_breakdown_from_text(api, ran):
    r = api.post("/jobs/breakdown", data={"text": "Fan flicks early", "player": "Fan Zhendong"})
    assert r.status_code == 201 and r.json()["params"]["stroke_type"] == "auto"
    assert ran["run_breakdown"][0] == (None, "Fan flicks early", "", "Fan Zhendong", "auto", "")


def test_breakdown_from_upload_with_stroke_type(api, ran, tmp_path):
    r = api.post("/jobs/breakdown", data={"stroke_type": "backhand_push", "hand": "left"}, files=VIDEO)
    assert r.status_code == 201
    path, text, stroke, player, hand, stroke_type = ran["run_breakdown"][0]
    assert path.read_bytes() == b"fake video bytes" and (hand, stroke_type) == ("left", "backhand_push")


def test_breakdown_from_link(api, ran, link_ok):
    r = api.post("/jobs/breakdown", data={"url": SHORT})
    assert r.status_code == 201 and r.json()["params"]["video"] == "Ma Long forehand"
    url, pipeline, *_ = ran["fetch_then"][0]
    assert url == CANONICAL and pipeline is main.run_breakdown


def test_breakdown_upload_wins_over_link(api, ran, monkeypatch):
    monkeypatch.setattr(download, "probe", lambda url: pytest.fail("the link should not be probed"))
    r = api.post("/jobs/breakdown", data={"url": SHORT}, files=VIDEO)
    assert r.status_code == 201 and "run_breakdown" in ran


def test_breakdown_ignores_empty_file_part(api, ran):
    """Browsers send an empty, unnamed file part when the input is left blank."""
    body = (b'--B\r\nContent-Disposition: form-data; name="text"\r\n\r\nloops\r\n'
            b'--B\r\nContent-Disposition: form-data; name="video"; filename=""\r\n'
            b"Content-Type: application/octet-stream\r\n\r\n\r\n--B--\r\n")
    r = api.post("/jobs/breakdown", content=body, headers={"content-type": "multipart/form-data; boundary=B"})
    assert r.status_code == 201 and ran["run_breakdown"][0][0] is None


# ------------------------------------------------------------------ POST /jobs/match

@pytest.mark.parametrize("data,expect", [
    ({"stroke": "serve"}, "forehand or backhand"),
    ({"hand": "both"}, "hand must be"),
    ({"height_cm": "tall"}, "number in cm"),
    ({"height_cm": "50"}, "between 100 and 230"),
])
def test_match_validation(api, ran, data, expect):
    r = api.post("/jobs/match", data=data, files=VIDEO)
    assert r.status_code == 400 and expect in _error(r)


def test_match_needs_a_video(api, ran):
    r = api.post("/jobs/match", data={"stroke": "forehand"})
    assert r.status_code == 400 and "Upload a clip of yourself" in _error(r)


def test_match_upload(api, ran):
    r = api.post("/jobs/match", data={"stroke": "backhand", "height_cm": "175"}, files=VIDEO)
    assert r.status_code == 201 and r.json()["params"]["height_cm"] == 175.0
    path, stroke, height, hand = ran["run_match"][0]
    assert (stroke, height, hand) == ("backhand", 175.0, "auto") and path.exists()


def test_match_link(api, ran, link_ok):
    r = api.post("/jobs/match", data={"url": SHORT, "stroke": "forehand"})
    assert r.status_code == 201
    assert ran["fetch_then"][0][:2] == (CANONICAL, main.run_match)


# ------------------------------------------------------------------ POST /jobs/coach

def test_coach_needs_a_request(api, ran):
    r = api.post("/jobs/coach", data={"request": "  "}, files=VIDEO)
    assert r.status_code == 400 and "Tell the coach" in _error(r)


def test_coach_needs_a_video(api, ran):
    r = api.post("/jobs/coach", data={"request": "fix my forehand"})
    assert r.status_code == 400 and "Add a video" in _error(r)


def test_coach_upload(api, ran):
    r = api.post("/jobs/coach", data={"request": "show my best rallies"}, files=VIDEO)
    assert r.status_code == 201 and r.json()["kind"] == "coach"
    path, url, request = ran["run_coach"][0]
    assert path.exists() and url is None and request == "show my best rallies"


def test_coach_link_is_passed_to_the_agent(api, ran, link_ok):
    r = api.post("/jobs/coach", data={"request": "fix my forehand", "url": SHORT})
    assert r.status_code == 201
    assert ran["run_coach"][0] == (None, CANONICAL, "fix my forehand")


# ------------------------------------------------------------------ GET /jobs/{id}

def test_unknown_job_is_404(api):
    assert api.get("/jobs/0123456789abcdef0123456789abcdef").status_code == 404


def test_running_job_is_reported_while_its_worker_is_alive(api):
    job = jobs.create("breakdown", {})
    jobs.update(job["id"], status="running", progress=0.4, message="running MediaPipe pose")
    got = api.get(f"/jobs/{job['id']}").json()
    assert (got["status"], got["progress"]) == ("running", 0.4)


def test_job_orphaned_by_a_restart_is_failed_not_left_running(api):
    """uvicorn --reload (or a crash) kills the worker; the record would say 'running' forever
    and the page would poll forever. After a restart the job is reported as failed."""
    job = jobs.create("breakdown", {})
    jobs.update(job["id"], status="running", progress=0.8, message="rendering")
    jobs.ACTIVE.clear()  # a new process knows nothing about the old worker
    got = api.get(f"/jobs/{job['id']}").json()
    assert got["status"] == "failed" and got["message"] == jobs.RESTARTED
    assert jobs.load(job["id"])["status"] == "failed"


def test_a_crashing_pipeline_fails_the_job(api):
    job = jobs.create("breakdown", {})

    def crash(job_id):
        raise ValueError("boom")

    jobs.run(crash, job["id"])
    got = api.get(f"/jobs/{job['id']}").json()
    assert got["status"] == "failed" and got["message"] == "boom" and job["id"] not in jobs.ACTIVE


def test_a_pipeline_that_returns_without_finishing_fails_the_job(api):
    job = jobs.create("breakdown", {})
    jobs.run(lambda job_id: jobs.update(job_id, status="running", progress=0.5), job["id"])
    got = api.get(f"/jobs/{job['id']}").json()
    assert got["status"] == "failed" and got["message"] == jobs.UNFINISHED


def test_polls_never_see_a_half_written_job(api):
    """job.json is replaced atomically; before, a poll during a write got a 500."""
    job = jobs.create("coach", {})
    stop, errors = threading.Event(), []

    def writer():
        i = 0
        while not stop.is_set():
            i += 1
            jobs.update(job["id"], progress=i / 1e6, message="x" * (i % 5000), todos=[{"content": "t"}] * (i % 50))

    t = threading.Thread(target=writer)
    t.start()
    try:
        for _ in range(400):
            r = api.get(f"/jobs/{job['id']}")
            if r.status_code != 200:
                errors.append(r.status_code)
    finally:
        stop.set()
        t.join()
    assert errors == []


# ------------------------------------------------------------------ GET /jobs/{id}/result and /files/{name}

def test_result_is_404_until_the_video_exists(api, tmp_path):
    job = jobs.create("breakdown", {})
    assert api.get(f"/jobs/{job['id']}/result").status_code == 404
    (tmp_path / job["id"] / "result.mp4").write_bytes(b"0123456789")
    r = api.get(f"/jobs/{job['id']}/result")
    assert r.status_code == 200 and r.headers["content-type"] == "video/mp4" and r.content == b"0123456789"


def test_result_supports_range_requests_for_ios(api, tmp_path):
    job = jobs.create("breakdown", {})
    (tmp_path / job["id"] / "result.mp4").write_bytes(b"0123456789")
    r = api.get(f"/jobs/{job['id']}/result", headers={"Range": "bytes=2-5"})
    assert r.status_code == 206 and r.content == b"2345"


@pytest.mark.parametrize("name", ["job.json", "..%2Fjob.json", "a b.mp4", "x.mov", ("a" * 70) + ".mp4"])
def test_files_only_serves_mp4_names(api, tmp_path, name):
    job = jobs.create("coach", {})
    (tmp_path / job["id"] / "job.json").write_text("{}")
    assert api.get(f"/jobs/{job['id']}/files/{name}").status_code == 404


def test_files_serves_the_coach_videos(api, tmp_path):
    job = jobs.create("coach", {})
    assert api.get(f"/jobs/{job['id']}/files/highlights.mp4").status_code == 404
    (tmp_path / job["id"] / "highlights.mp4").write_bytes(b"mp4")
    assert api.get(f"/jobs/{job['id']}/files/highlights.mp4").content == b"mp4"
    assert api.get("/jobs/not-a-job-id/files/highlights.mp4").status_code == 404


# ------------------------------------------------------------------ end to end (real pipelines)

def test_text_breakdown_end_to_end(api, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = api.post("/jobs/breakdown", data={"text": "He chops from far back", "player": "Ding Ning"})
    job = api.get(f"/jobs/{r.json()['id']}").json()
    assert job["status"] == "done", job["message"]
    assert job["strokeType"]["key"] == "chop" and len(job["breakdown"]["steps"]) == 3
    assert len(api.get(f"/jobs/{job['id']}/result").content) > 10_000


def test_video_breakdown_always_finishes(api, tmp_path, monkeypatch):
    """A clip with no player in it must end done or failed, never stay running."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    clip = tmp_path / "empty.mp4"
    wr = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"mp4v"), 30, (640, 360))
    for i in range(60):
        frame = np.full((360, 640, 3), 40, np.uint8)
        cv2.circle(frame, (50 + i * 9, 180), 20, (255, 255, 255), -1)
        wr.write(frame)
    wr.release()
    with clip.open("rb") as f:
        r = api.post("/jobs/breakdown", files={"video": ("empty.mp4", f, "video/mp4")})
    job = api.get(f"/jobs/{r.json()['id']}").json()
    assert job["status"] in ("done", "failed") and job["message"]
    assert job["id"] not in jobs.ACTIVE


@pytest.mark.skipif(not os.environ.get("TTSKILL_NETWORK"), reason="set TTSKILL_NETWORK=1 to hit YouTube")
def test_link_breakdown_end_to_end(api, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = api.post("/jobs/breakdown", data={"url": SHORT, "player": "Ma Long"})
    assert r.status_code == 201, r.text
    job = api.get(f"/jobs/{r.json()['id']}").json()
    assert job["status"] == "done", job["message"]
    assert not list((jobs.job_dir(job["id"])).glob("input.*"))  # the download is deleted
