"""The breakdown job runs the real technique pipeline (text path: no video, no API key)."""
from app import jobs, pipelines


def test_text_breakdown_job(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    job = jobs.create("breakdown", {"stroke": "flick"})
    pipelines.run_breakdown(job["id"], None, "Fan Zhendong flicks with a high elbow and a fast wrist snap.",
                            "flick", "Fan Zhendong")
    done = jobs.load(job["id"])
    assert done["status"] == "done", done["message"]
    assert done["resultUrl"] == f"/jobs/{job['id']}/result"
    assert (tmp_path / job["id"] / "result.mp4").stat().st_size > 0
    assert len(done["breakdown"]["steps"]) == 3
