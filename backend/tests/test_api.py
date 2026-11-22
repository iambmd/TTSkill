"""Every API endpoint: input validation (422s with a message the user can act on), what gets
scheduled, job records, result and file serving, and that a job can never stay
queued/running forever (the "breakdown just sits there" bug). Pipelines are replaced by
recorders except in the end-to-end tests at the end."""
import os
import threading
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import download, jobs, main, validate

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
        def run(job_id, *args, **kwargs):
            # Keyword arguments (only_me) are recorded after the positional ones, only when given.
            calls.setdefault(name, []).append(args + ((kwargs,) if kwargs else ()))
            jobs.update(job_id, status="done", progress=1.0)
        return run

    for name in ("run_autocut", "run_breakdown", "run_match", "fetch_then"):
        monkeypatch.setattr(main, name, recorder(name))
    import agent.coach
    monkeypatch.setattr(agent.coach, "run_coach", recorder("run_coach"))
    return calls


@pytest.fixture
def link_ok(monkeypatch):
    kinds = []

    def probe(url, kind):
        kinds.append(kind)
        return {"id": "g3n9jVP0fMU", "title": "Ma Long forehand", "duration": 32, "url": download.canonical(url)}
    monkeypatch.setattr(download, "probe", probe)
    return kinds


def _error(r) -> str:
    return r.json()["detail"]


# ------------------------------------------------------------------ health

def test_health(api):
    assert api.get("/health").json() == {"ok": True}


@pytest.mark.parametrize("origin, allowed", [
    ("https://ttskill.vercel.app", True),
    ("https://ttskill-git-feat-x-team.vercel.app", True),
    ("https://shy-river-1234.trycloudflare.com", True),
    ("http://localhost:3000", True),
    ("https://evil.example", False),
    ("https://ttskill.vercel.app.evil.example", False),
    ("https://evilvercel.app", False),
    ("http://ttskill.vercel.app", False),
])
def test_cors_allows_vercel_tunnel_and_localhost(api, origin, allowed):
    # Upload progress listeners make the browser send a preflight before the multipart POST.
    pre = api.options("/jobs/autocut", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
    got = api.get("/health", headers={"Origin": origin})
    assert (pre.headers.get("access-control-allow-origin") == origin) is allowed
    assert (got.headers.get("access-control-allow-origin") == origin) is allowed


# ------------------------------------------------------------------ POST /jobs/autocut

def test_autocut_needs_a_video_or_link(api, ran):
    r = api.post("/jobs/autocut", data={"mode": "highlights"})
    assert r.status_code == 422 and "Upload a match video or paste a YouTube link" in _error(r)
    assert not ran


@pytest.mark.parametrize("data,expect", [
    ({"mode": "best"}, "Mode must be highlights or full"),
    ({"top_n": "0"}, "Rallies in the reel must be between 1 and 20"),
    ({"top_n": "abc"}, "Rallies in the reel must be a whole number"),
    ({"threshold": "0.5"}, "Hit threshold must be between 1.5 and 10"),
    ({"threshold": "nan"}, "Hit threshold must be between"),
    ({"gap": "-1"}, "Max gap must be between 0.5 and 5"),
    ({"min_hits": "1"}, "Min hits must be between 2 and 20"),
    ({"min_hits": "2.5"}, "Min hits must be a whole number"),
])
def test_autocut_settings_must_be_in_range(api, ran, upload, data, expect):
    r = api.post("/jobs/autocut", data=data, files=upload())
    assert r.status_code == 422 and expect in _error(r)
    assert not ran


def test_autocut_rejects_links_that_are_not_youtube(api, ran):
    r = api.post("/jobs/autocut", data={"url": "https://vimeo.com/123"})
    assert r.status_code == 422 and "Only YouTube links work here" in _error(r)


def test_autocut_private_video_fails_on_the_form(api, ran, monkeypatch):
    def private(url, kind):
        raise download.LinkError("That video is private. Use a public or unlisted video.")
    monkeypatch.setattr(download, "probe", private)
    r = api.post("/jobs/autocut", data={"url": SHORT})
    assert r.status_code == 422 and "private" in _error(r)
    assert not ran


def test_autocut_upload_saves_the_file_and_runs_the_pipeline(api, ran, tmp_path, media, upload):
    r = api.post("/jobs/autocut", data={"mode": "full", "top_n": "3", "threshold": "2.5"}, files=upload())
    assert r.status_code == 201
    job = r.json()
    assert job["kind"] == "autocut" and job["status"] == "queued" and job["params"]["mode"] == "full"
    path, *rest = ran["run_autocut"][0]
    assert path == tmp_path / job["id"] / "input.mp4" and path.read_bytes() == media["ok"].read_bytes()
    assert not list((tmp_path / ".uploads").iterdir())  # moved into the job, not copied
    assert rest == ["full", 3, 2.5, 1.6, 4]
    assert api.get(f"/jobs/{job['id']}").json()["status"] == "done"


def test_autocut_link_is_downloaded_first(api, ran, link_ok):
    r = api.post("/jobs/autocut", data={"url": SHORT, "mode": "highlights"})
    assert r.status_code == 201 and r.json()["params"]["url"] == CANONICAL
    url, pipeline, *rest = ran["fetch_then"][0]
    assert url == CANONICAL and pipeline is main.run_autocut and rest[0] == "highlights"
    assert link_ok == ["autocut"]  # probed against Auto-Cut's 60-minute limit


# ------------------------------------------------------------------ POST /jobs/breakdown

@pytest.mark.parametrize("data,expect", [
    ({"text": "loops", "stroke": "smash"}, "Unknown stroke: smash"),
    ({"text": "loops", "stroke_type": "tomahawk"}, "Unknown stroke type: tomahawk"),
    ({"text": "loops", "hand": "both"}, "Bat hand must be auto, left or right"),
    ({}, "Upload a clip, paste a YouTube link, or describe the training"),
    ({"text": "   "}, "Upload a clip"),
    ({"text": "x" * 5001}, "The training description can be up to 5000 characters (it has 5001)"),
    ({"text": "loops", "player": "M" * 81}, "The player's name can be up to 80 characters"),
    ({"url": "https://www.youtube.com/playlist?list=PL123"}, "That's a playlist"),
    ({"url": "https://www.youtube.com/@pingskills"}, "That's a channel link"),
])
def test_breakdown_validation(api, ran, data, expect):
    r = api.post("/jobs/breakdown", data=data)
    assert r.status_code == 422 and expect in _error(r)
    assert not ran


def test_breakdown_from_text(api, ran):
    r = api.post("/jobs/breakdown", data={"text": "Fan flicks early", "player": "Fan Zhendong"})
    assert r.status_code == 201 and r.json()["params"]["stroke_type"] == "auto"
    assert ran["run_breakdown"][0] == (None, "Fan flicks early", "", "Fan Zhendong", "auto", "")


def test_breakdown_from_upload_with_stroke_type(api, ran, media, upload):
    r = api.post("/jobs/breakdown", data={"stroke_type": "backhand_push", "hand": "left"}, files=upload())
    assert r.status_code == 201
    path, text, stroke, player, hand, stroke_type = ran["run_breakdown"][0]
    assert path.read_bytes() == media["ok"].read_bytes() and (hand, stroke_type) == ("left", "backhand_push")


def test_breakdown_from_link(api, ran, link_ok):
    r = api.post("/jobs/breakdown", data={"url": SHORT})
    assert r.status_code == 201 and r.json()["params"]["video"] == "Ma Long forehand"
    url, pipeline, *_ = ran["fetch_then"][0]
    assert url == CANONICAL and pipeline is main.run_breakdown and link_ok == ["breakdown"]


def test_breakdown_link_over_3_minutes_fails_on_the_form(api, ran, monkeypatch):
    def long_video(url, kind):
        download.check_info({"duration": 200}, kind)
    monkeypatch.setattr(download, "probe", long_video)
    r = api.post("/jobs/breakdown", data={"url": SHORT})
    assert r.status_code == 422 and "3:20 long. Use one under 3 minutes" in _error(r)
    assert not ran


def test_breakdown_upload_wins_over_link(api, ran, monkeypatch, upload):
    monkeypatch.setattr(download, "probe", lambda url, kind: pytest.fail("the link should not be probed"))
    r = api.post("/jobs/breakdown", data={"url": SHORT}, files=upload())
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
    ({"stroke": "serve"}, "Stroke must be forehand or backhand"),
    ({"hand": "both"}, "Bat hand must be auto, left or right"),
    ({"grip": "seemiller"}, "Grip must be shakehand or penhold"),
    ({"height_cm": "tall"}, "as a number in cm"),
    ({"height_cm": "-170"}, "as a number in cm"),
    ({"height_cm": "0"}, "between 100 and 230"),
    ({"height_cm": "50"}, "between 100 and 230"),
    ({"height_cm": "250"}, "between 100 and 230"),
    ({"height_cm": "230.5"}, "between 100 and 230"),
    ({"height_cm": "nan"}, "as a number in cm"),
    ({"height_cm": "1e2"}, "as a number in cm"),
])
def test_match_validation(api, ran, upload, data, expect):
    r = api.post("/jobs/match", data=data, files=upload())
    assert r.status_code == 422 and expect in _error(r)
    assert not ran


def test_match_needs_a_video(api, ran):
    r = api.post("/jobs/match", data={"stroke": "forehand"})
    assert r.status_code == 422 and "Upload a clip of yourself" in _error(r)


@pytest.mark.parametrize("height", ["100", "175", "230", " 182.5 "])
def test_match_upload(api, ran, upload, height):
    r = api.post("/jobs/match", data={"stroke": "backhand", "height_cm": height, "grip": "penhold"}, files=upload())
    assert r.status_code == 201 and r.json()["params"]["height_cm"] == float(height)
    path, stroke, h, hand, grip = ran["run_match"][0]
    assert (stroke, h, hand, grip) == ("backhand", float(height), "auto", "penhold") and path.exists()


def test_match_grip_defaults_to_shakehand(api, ran, upload):
    assert api.post("/jobs/match", files=upload()).json()["params"]["grip"] == "shakehand"
    assert ran["run_match"][0][-1] == "shakehand"


def test_match_link(api, ran, link_ok):
    r = api.post("/jobs/match", data={"url": SHORT, "stroke": "forehand"})
    assert r.status_code == 201
    assert ran["fetch_then"][0][:2] == (CANONICAL, main.run_match) and link_ok == ["match"]


# ------------------------------------------------------------------ POST /jobs/coach

@pytest.mark.parametrize("data", [{"request": "  "}, {"request": "\n\t"}, {}])
def test_coach_needs_a_request(api, ran, upload, data):
    r = api.post("/jobs/coach", data=data, files=upload())
    assert r.status_code == 422 and "Tell the coach" in _error(r)
    assert not ran


def test_coach_request_is_at_most_1000_characters(api, ran, upload):
    r = api.post("/jobs/coach", data={"request": "a" * 1001}, files=upload())
    assert r.status_code == 422 and "up to 1000 characters (it has 1001)" in _error(r)
    r = api.post("/jobs/coach", data={"request": "  " + "a" * 1000 + "  "}, files=upload())
    assert r.status_code == 201 and len(ran["run_coach"][0][2]) == 1000  # counted after trimming


def test_coach_needs_a_video(api, ran):
    r = api.post("/jobs/coach", data={"request": "fix my forehand"})
    assert r.status_code == 422 and "Add a video" in _error(r)


def test_coach_upload(api, ran, upload):
    r = api.post("/jobs/coach", data={"request": "show my best rallies"}, files=upload())
    assert r.status_code == 201 and r.json()["kind"] == "coach"
    path, url, request = ran["run_coach"][0]
    assert path.exists() and url is None and request == "show my best rallies"


def test_coach_link_is_passed_to_the_agent(api, ran, link_ok):
    r = api.post("/jobs/coach", data={"request": "fix my forehand", "url": SHORT})
    assert r.status_code == 201
    assert ran["run_coach"][0] == (None, CANONICAL, "fix my forehand") and link_ok == ["coach"]


# ------------------------------------------------------------------ uploads: checked before any job exists

@pytest.mark.parametrize("name,filename,expect", [
    ("ok", "clip.avi", "Upload a video file: MP4, MOV, WebM or MKV"),
    ("ok", "notes.txt", "Upload a video file"),
    ("ok", "clip", "Upload a video file"),
    ("short", "clip.mp4", "only 1.0 s long. Upload at least 2 seconds"),
    ("tiny", "clip.mp4", "only 320x180, too small to see the stroke. Re-record it"),
    ("sound_only", "clip.mp4", "no video track, only sound"),
])
@pytest.mark.parametrize("endpoint,data", [
    ("/jobs/autocut", {}), ("/jobs/breakdown", {}), ("/jobs/match", {}), ("/jobs/coach", {"request": "cut it"}),
])
def test_bad_uploads_are_rejected_everywhere(api, ran, tmp_path, upload, name, filename, expect, endpoint, data):
    r = api.post(endpoint, data=data, files=upload(name, filename))
    assert r.status_code == 422 and expect in _error(r)
    assert not ran and not [d for d in tmp_path.iterdir() if d.name != ".uploads"]  # no job was created
    staged = tmp_path / ".uploads"
    assert not (staged.exists() and any(staged.iterdir()))  # and the rejected file is deleted


def test_unreadable_upload(api, ran):
    r = api.post("/jobs/match", files={"video": ("clip.mov", b"not really a video", "video/quicktime")})
    assert r.status_code == 422 and "couldn't read that file as a video" in _error(r)


def test_upload_limits_come_from_the_shared_file(api, ran, upload, monkeypatch):
    monkeypatch.setitem(validate.LIMITS["upload"], "max_seconds", 2)
    r = api.post("/jobs/match", files=upload())
    assert r.status_code == 422 and "0:03 long. Uploads can be up to" in _error(r)
    monkeypatch.setitem(validate.LIMITS["upload"], "max_mb", 0.001)
    r = api.post("/jobs/match", files=upload())
    assert r.status_code == 422 and "Upload one under 0.001 MB" in _error(r)


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
    for i in range(90):
        frame = np.full((360, 640, 3), 40, np.uint8)
        cv2.circle(frame, (50 + i * 9, 180), 20, (255, 255, 255), -1)
        wr.write(frame)
    wr.release()
    with clip.open("rb") as f:
        r = api.post("/jobs/breakdown", files={"video": ("empty.mp4", f, "video/mp4")})
    job = api.get(f"/jobs/{r.json()['id']}").json()
    assert job["status"] == "failed" and "couldn't find a player in this clip" in job["message"]
    assert job["id"] not in jobs.ACTIVE


@pytest.mark.skipif(not os.environ.get("TTSKILL_NETWORK"), reason="set TTSKILL_NETWORK=1 to hit YouTube")
def test_link_breakdown_end_to_end(api, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = api.post("/jobs/breakdown", data={"url": SHORT, "player": "Ma Long"})
    assert r.status_code == 201, r.text
    job = api.get(f"/jobs/{r.json()['id']}").json()
    assert job["status"] == "done", job["message"]
    assert not list((jobs.job_dir(job["id"])).glob("input.*"))  # the download is deleted


# ------------------------------------------------------------------ Auto-Cut: too few rallies is advice, not an error

def test_autocut_with_no_rallies_warns_instead_of_failing(api, monkeypatch, media):
    from app import pipelines
    monkeypatch.setattr(pipelines, "detect_rallies", lambda *a: [])
    job = jobs.create("autocut", {})
    jobs.run(pipelines.run_autocut, job["id"], media["ok"], "highlights", 5, 3.0, 1.6, 4)
    got = api.get(f"/jobs/{job['id']}").json()
    assert got["status"] == "done" and got["resultUrl"] is None and got["rallies"] == []
    assert "didn't hear any rallies" in got["warning"] and "closer to the table" in got["warning"]


def test_autocut_with_one_rally_cuts_it_and_warns(api, monkeypatch, media):
    from app import pipelines
    from app.rally import Rally
    monkeypatch.setattr(pipelines, "detect_rallies", lambda *a: [Rally(0.5, 2.0, 6)])
    def filtered(video, rs, *, min_hits, progress):
        assert min_hits == 6
        progress(1, 1)
        return rs, []
    monkeypatch.setattr("app.floor_bounce.drop_non_play", filtered)
    job = jobs.create("autocut", {})
    jobs.run(pipelines.run_autocut, job["id"], media["ok"], "full", 5, 3.0, 1.6, 6)
    got = api.get(f"/jobs/{job['id']}").json()
    assert got["status"] == "done" and got["resultUrl"] and "only heard 1 rally" in got["warning"]
    assert api.get(f"/jobs/{job['id']}/result").status_code == 200
    assert got["autocutStage"] == {"key": "done"}
    assert api.get(got["previewUrl"], headers={"Range": "bytes=0-9"}).status_code == 206


# ------------------------------------------------------------------ players

def _jpeg() -> bytes:
    return cv2.imencode(".jpg", np.zeros((90, 160, 3), np.uint8))[1].tobytes()


def test_detect_players_validates_frames(api):
    assert "at least one frame" in _error(api.post("/players/detect", data={"times": ""}))
    many = [("frames", (f"f{i}.jpg", _jpeg(), "image/jpeg")) for i in range(17)]
    assert "at most 16 frames" in _error(api.post("/players/detect", files=many, data={"times": ",".join("1" * 17)}))
    one = [("frames", ("f.jpg", _jpeg(), "image/jpeg"))]
    assert "its time" in _error(api.post("/players/detect", files=one, data={"times": ""}))
    text = [("frames", ("f.jpg", b"not an image", "image/jpeg"))]
    assert "JPEG or PNG" in _error(api.post("/players/detect", files=text, data={"times": "1.5"}))
    assert "kind must be" in _error(api.post("/players/detect", files=one, data={"times": "1", "kind": "autocut"}))


def test_detect_players_runs_on_the_sent_frames(api, monkeypatch):
    from technique import people
    seen = {}

    def fake(frames, cancel=None):
        seen["frames"] = [(t, img.shape) for t, img in frames]
        return {"candidates": [], "frame": None, "suggested": None, "decisive": True}
    monkeypatch.setattr(people, "detect", fake)
    files = [("frames", ("a.jpg", _jpeg(), "image/jpeg")), ("frames", ("b.jpg", _jpeg(), "image/jpeg"))]
    r = api.post("/players/detect", files=files, data={"times": "1.5,30"})
    assert r.status_code == 200 and r.json()["decisive"]
    assert seen["frames"] == [(1.5, (90, 160, 3)), (30.0, (90, 160, 3))]


def test_jobs_take_the_tapped_player_only_when_there_is_one(api, ran, upload):
    pick = {"player_time": "12.5", "player_box": "0.1,0.2,0.4,0.9"}
    r = api.post("/jobs/match", files=upload(), data={"stroke": "forehand", **pick})
    assert r.status_code == 201 and r.json()["params"]["player_pick"] == {"time": 12.5, "box": [0.1, 0.2, 0.4, 0.9]}
    assert ran["run_match"][0][-1] == (12.5, (0.1, 0.2, 0.4, 0.9))
    api.post("/jobs/breakdown", files=upload(), data=pick)
    assert ran["run_breakdown"][0][-1] == (12.5, (0.1, 0.2, 0.4, 0.9))
    api.post("/jobs/coach", files=upload(), data={"request": "fix my forehand", **pick})
    assert ran["run_coach"][0][-1] == (12.5, (0.1, 0.2, 0.4, 0.9))
    r = api.post("/jobs/match", files=upload(), data={"stroke": "forehand"})
    assert len(ran["run_match"][1]) == 5 and "player_pick" not in r.json()["params"]


def test_a_broken_player_pick_is_a_422(api, ran, upload):
    r = api.post("/jobs/match", files=upload(), data={"player_time": "3", "player_box": "0.5,0,0.4,1"})
    assert r.status_code == 422 and "Pick the player again" in _error(r) and not ran


def test_change_player_reruns_the_same_job_on_the_stored_video(api, ran, upload):
    first = api.post("/jobs/match", files=upload(), data={"stroke": "backhand", "grip": "penhold", "height_cm": "168"}).json()
    r = api.post(f"/jobs/{first['id']}/rerun", data={"player_time": "3.5", "player_box": "0.5,0.2,0.7,0.9"})
    assert r.status_code == 201, r.text
    again = r.json()
    assert again["kind"] == "match" and again["id"] != first["id"]
    assert again["params"]["rerun_of"] == first["id"] and again["params"]["player_pick"]["time"] == 3.5
    path, stroke, height, hand, grip, selection = ran["run_match"][-1]
    assert (stroke, height, grip, selection) == ("backhand", 168.0, "penhold", (3.5, (0.5, 0.2, 0.7, 0.9)))
    assert path.parent.name == again["id"] and path.exists()   # its own copy of the upload


def test_change_player_needs_a_pick_and_a_kind_that_tracks_one(api, ran, upload):
    first = api.post("/jobs/autocut", files=upload(), data={}).json()
    pick = {"player_time": "1", "player_box": "0,0,1,1"}
    assert "Pick the player again" in _error(api.post(f"/jobs/{first['id']}/rerun", data={}))
    assert "Only Breakdown" in _error(api.post(f"/jobs/{first['id']}/rerun", data=pick))
    assert "Unknown job" in _error(api.post("/jobs/not-a-job/rerun", data=pick))


def test_detect_players_on_a_jobs_stored_video(api, ran, upload, monkeypatch):
    from technique import people
    first = api.post("/jobs/coach", files=upload(), data={"request": "fix my forehand"}).json()
    seen = {}
    monkeypatch.setattr(people, "sample_frames", lambda path, count=6: seen.setdefault("path", path) and [])
    monkeypatch.setattr(people, "detect", lambda frames, cancel=None: {"candidates": [], "frame": None, "suggested": None, "decisive": True})
    r = api.post("/players/detect", data={"job": first["id"], "kind": "coach"})
    assert r.status_code == 200 and seen["path"].endswith(".mp4") and first["id"] in seen["path"]


def test_detect_work_is_cancelled_when_the_browser_disconnects():
    import asyncio
    import threading
    import time

    started, stopped = threading.Event(), threading.Event()

    def slow(cancel):
        started.set()
        while not cancel.is_set():   # a detection loop checks this between frames
            time.sleep(.01)
        stopped.set()
        return "nobody reads this"

    class Browser:
        polls = 0

        async def is_disconnected(self):
            self.polls += 1
            return self.polls > 1    # still there at the first check, gone at the second

    async def go():
        with pytest.raises(main.ClientGone):
            await main.run_while_connected(Browser(), slow)
    asyncio.run(go())
    assert started.is_set() and stopped.wait(2), "the worker kept going after the disconnect"


def test_detect_returns_while_connected():
    import asyncio

    class Browser:
        async def is_disconnected(self):
            return False

    async def go():
        return await main.run_while_connected(Browser(), lambda x, cancel: x * 2, 21)
    assert asyncio.run(go()) == 42


def test_detect_reports_where_the_time_went(api, monkeypatch, caplog):
    import logging
    from technique import people

    def fake(frames, cancel=None):
        return {"candidates": [{"id": 0}], "frame": None, "suggested": 0, "decisive": True,
                "frames": [{"time": t, "people": 1} for t, _ in frames], "timing": {"seconds": 0.0, "frames": len(frames)}}
    monkeypatch.setattr(people, "detect", fake)
    files = [("frames", ("a.jpg", _jpeg(), "image/jpeg")), ("frames", ("b.jpg", _jpeg(), "image/jpeg"))]
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        t = api.post("/players/detect", files=files, data={"times": "1.5,30", "grab_ms": "480"}).json()["timing"]
    assert {"read_s", "wait_s", "decode_s", "total_s", "seconds"} <= set(t) and t["total_s"] >= t["seconds"] - 0.01
    line = next(r.getMessage() for r in caplog.records if "players/detect" in r.getMessage())
    assert "2 frames [1.5s:1 30.0s:1] -> 1 players" in line and "decode" in line


def test_a_link_is_probed_off_the_event_loop(api, monkeypatch):
    """yt-dlp's probe takes seconds; on the event loop it froze every other request."""
    import asyncio
    from technique import people
    where = {}

    def probe(url, kind):
        try:
            asyncio.get_running_loop()
            where["on_loop"] = True
        except RuntimeError:
            where["on_loop"] = False
        return {"id": "x", "title": "t", "duration": 30, "url": download.canonical(url)}
    monkeypatch.setattr(download, "probe", probe)
    monkeypatch.setattr(download, "download", lambda url, folder, progress=None: folder / "input.mp4")
    monkeypatch.setattr(people, "sample_frames", lambda path, count=6: [])
    monkeypatch.setattr(people, "detect", lambda frames, cancel=None: {"candidates": [], "timing": {"seconds": 0}})
    r = api.post("/players/detect", data={"url": SHORT, "kind": "coach"})
    assert r.status_code == 200 and where == {"on_loop": False} and "probe_s" in r.json()["timing"]


def test_a_link_download_stops_when_the_browser_leaves(tmp_path, monkeypatch):
    from technique import people
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    cancel = threading.Event()

    def fetch(url, folder, progress=None):
        cancel.set()          # the browser leaves mid-download...
        progress(0.3)         # ...and the next progress report stops it
        raise AssertionError("the download kept going")
    monkeypatch.setattr(download, "download", fetch)
    with pytest.raises(people.Cancelled):
        main._detect_video(None, CANONICAL, 0.0, cancel=cancel)
    assert not any((tmp_path / ".players").iterdir())   # its folder is gone too


def test_startup_loads_the_pose_model_on_every_detection_thread(monkeypatch):
    from technique import people
    warmed = []
    monkeypatch.setattr(people, "warm", lambda: warmed.append(threading.current_thread().name))
    main.warm_players()
    for _ in range(50):
        if len(warmed) == main.PLAYER_THREADS:
            break
        threading.Event().wait(0.05)
    assert len(set(warmed)) == main.PLAYER_THREADS



def test_only_me_skips_the_pick_and_follows_whoever_plays_the_most(api, ran, upload):
    r = api.post("/jobs/breakdown", files=upload(), data={"only_me": "1"})
    assert r.status_code == 201 and r.json()["params"]["only_me"] is True
    assert ran["run_breakdown"][-1][-1] == {"only_me": True}
    r = api.post("/jobs/coach", files=upload(), data={"request": "fix my forehand", "only_me": "1"})
    assert r.json()["params"]["only_me"] is True and ran["run_coach"][-1][-1] == {"only_me": True}
    # Unticked: nothing changes for the pipelines.
    api.post("/jobs/breakdown", files=upload(), data={"only_me": ""})
    assert not isinstance(ran["run_breakdown"][-1][-1], dict)


def test_a_tapped_player_wins_over_only_me(api, ran, upload):
    pick = {"player_time": "2", "player_box": "0.1,0.2,0.4,0.9", "only_me": "1"}
    r = api.post("/jobs/coach", files=upload(), data={"request": "fix my forehand", **pick})
    assert "only_me" not in r.json()["params"] and ran["run_coach"][-1][-1] == (2.0, (0.1, 0.2, 0.4, 0.9))


def test_only_me_must_be_ticked_or_not(api, ran, upload):
    r = api.post("/jobs/breakdown", files=upload(), data={"only_me": "yes"})
    assert r.status_code == 422 and "Only me in the video" in _error(r) and not ran



# ------------------------------------------------------------------ the browser can't read the video

@pytest.fixture(scope="module")
def hevc(tmp_path_factory) -> Path:
    """An iPhone-like HEVC .mov (Chrome without an HEVC decoder can't draw its frames)."""
    import subprocess
    out = tmp_path_factory.mktemp("hevc") / "IMG_0001.MOV"
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=4",
                        "-f", "lavfi", "-i", "sine=frequency=3000:duration=4", "-c:v", "libx265", "-tag:v", "hvc1",
                        "-x265-params", "log-level=error", "-c:a", "aac", "-shortest", str(out)], check=True)
    except subprocess.CalledProcessError:
        pytest.skip("ffmpeg has no libx265")
    return out


def test_a_video_the_browser_cant_read_is_read_on_the_server_and_kept_for_the_job(api, ran, hevc, monkeypatch):
    from technique import people
    seen = {}

    def fake(frames, cancel=None):
        seen["frames"] = [(t, img.shape) for t, img in frames]
        return {"candidates": [{"id": 0}], "others": [], "frame": None, "timing": {"seconds": 0.1}}
    monkeypatch.setattr(people, "detect", fake)
    r = api.post("/players/detect", files={"video": ("IMG_0001.MOV", hevc.read_bytes(), "video/quicktime")},
                 data={"kind": "breakdown"})
    assert r.status_code == 200, r.text
    # ffmpeg decoded the HEVC frames: 12 spread over the 4 s.
    assert len(seen["frames"]) == 12 and seen["frames"][0][1] == (360, 640, 3)
    assert seen["frames"][0][0] < .5 and seen["frames"][-1][0] > 3.5
    token = r.json()["staged"]
    assert "stage_s" in r.json()["timing"]
    # The job takes the kept upload: no second upload of the file.
    pick = {"player_time": "1", "player_box": "0.1,0.1,0.5,0.9"}
    job = api.post("/jobs/breakdown", data={"staged": token, **pick})
    assert job.status_code == 201, job.text
    assert job.json()["params"]["video"] == "IMG_0001.MOV"
    path = ran["run_breakdown"][-1][0]
    assert path.name == "input.mov" and path.read_bytes() == hevc.read_bytes()
    # It is used once.
    again = api.post("/jobs/coach", data={"staged": token, "request": "fix my forehand"})
    assert again.status_code == 422 and "expired" in _error(again)


def test_a_kept_upload_needs_a_real_token(api, ran):
    assert "Choose the video again" in _error(api.post("/jobs/match", data={"staged": "../../etc/passwd"}))
    assert "expired" in _error(api.post("/jobs/match", data={"staged": "0" * 32 + ".mov"}))
    assert not ran


def test_kept_uploads_are_deleted_after_two_hours(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    staging = tmp_path / ".uploads"
    staging.mkdir()
    old, new = staging / ("a" * 32 + ".mov"), staging / ("b" * 32 + ".mov")
    old.write_bytes(b"x")
    new.write_bytes(b"y")
    os.utime(old, (0, 0))
    assert main.keep_for_job(new, "clip.mov") == new.name
    assert not old.exists() and new.exists()
    assert main.staged_input(new.name) == (new, "clip.mov")


def test_detect_checks_an_uploaded_video_like_a_job_upload(api, upload):
    r = api.post("/players/detect", files={"video": ("notes.txt", b"hello", "text/plain")}, data={"kind": "coach"})
    assert r.status_code == 422


@pytest.mark.parametrize("kind,fields", [("coach", {"request": "Fix my forehand"}), ("breakdown", {})])
def test_autocut_upload_can_start_an_analysis_without_another_upload(api, ran, upload, kind, fields):
    original = api.post("/jobs/autocut", files=upload()).json()
    assert api.get(f"/jobs/{original['id']}").json()["canReuseVideo"] is True
    response = api.post(f"/jobs/{kind}", data={**fields, "source_job": original["id"]})
    assert response.status_code == 201, response.text
    child = response.json()
    assert child["params"]["source_job"] == original["id"]
    path = ran[f"run_{kind}"][-1][0]
    assert path.parent.name == child["id"]
    assert path.read_bytes() == ran["run_autocut"][-1][0].read_bytes()

    bad = api.post(f"/jobs/{kind}", data={**fields, "source_job": child["id"]})
    assert bad.status_code == 422
