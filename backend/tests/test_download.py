"""Pasted YouTube links: parsing, friendly errors, and the download -> pipeline -> cleanup flow."""
import os

import pytest

from app import download, jobs, pipelines

SHORT = "https://youtube.com/shorts/g3n9jVP0fMU"  # Ma Long forehand, 32 s


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=g3n9jVP0fMU",
    "https://youtube.com/watch?feature=share&v=g3n9jVP0fMU&t=3",
    "https://m.youtube.com/watch?v=g3n9jVP0fMU",
    "https://youtu.be/g3n9jVP0fMU?si=abc",
    SHORT,
    "youtube.com/shorts/g3n9jVP0fMU?feature=share",
])
def test_accepts_watch_youtu_be_and_shorts(url):
    assert download.video_id(url) == "g3n9jVP0fMU"
    assert download.canonical(url) == "https://www.youtube.com/watch?v=g3n9jVP0fMU"


@pytest.mark.parametrize("url", ["", "hello", "https://vimeo.com/123", "https://www.youtube.com/@swift_TT",
                                 "https://www.youtube.com/watch?v=short", "https://evil.com/youtu.be/g3n9jVP0fMU"])
def test_rejects_other_links(url):
    with pytest.raises(download.LinkError):
        download.video_id(url)


@pytest.mark.parametrize("raw,expect", [
    ("ERROR: [youtube] x: Private video. Sign in if you've been granted access", "private"),
    ("ERROR: [youtube] x: This video is unavailable", "unavailable"),
    ("ERROR: [youtube] x: Sign in to confirm your age", "age-restricted"),
])
def test_friendly_errors(raw, expect):
    assert expect in str(download._friendly(Exception(raw)))


def test_fetch_then_runs_pipeline_and_deletes_download(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    job = jobs.create("autocut", {})

    def fake_download(url, dest, progress=None):
        progress(1.0)
        p = dest / "input.mp4"
        p.write_bytes(b"video")
        return p

    seen = {}

    def fake_run(job_id, path, *args):
        seen["exists"], seen["args"] = path.exists(), args
        jobs.update(job_id, status="done")

    monkeypatch.setattr(pipelines, "download", fake_download)
    pipelines.fetch_then(job["id"], SHORT, fake_run, "highlights", 5)
    assert seen == {"exists": True, "args": ("highlights", 5)}
    assert not (tmp_path / job["id"] / "input.mp4").exists()
    assert jobs.load(job["id"])["status"] == "done"


def test_fetch_then_reports_download_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    job = jobs.create("autocut", {})

    def boom(*_a, **_k):
        raise download.LinkError("That video is private. Use a public or unlisted video.")

    monkeypatch.setattr(pipelines, "download", boom)
    pipelines.fetch_then(job["id"], SHORT, lambda *a: pytest.fail("should not run"))
    done = jobs.load(job["id"])
    assert done["status"] == "failed" and "private" in done["message"]


@pytest.mark.skipif(not os.environ.get("TTSKILL_NETWORK"), reason="set TTSKILL_NETWORK=1 to hit YouTube")
def test_real_short(tmp_path):
    info = download.probe(SHORT)
    assert 0 < info["duration"] <= download.MAX_SECONDS
    path = download.download(SHORT, tmp_path)
    assert path.suffix == ".mp4" and path.stat().st_size > 100_000
