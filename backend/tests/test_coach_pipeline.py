"""Coach's fixed pipeline (Phase 1): the one cached Claude call, the flow and its partial results."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from technique.pose import PoseTrack


def test_the_coaching_prompt_is_static_and_cached():
    from agent import brief
    a, b = brief.system_blocks(), brief.system_blocks()
    assert a == b and a[0]["cache_control"] == {"type": "ephemeral"}
    text = a[0]["text"]
    assert "Ma Long" in text and "forehand_topspin" in text and "Exactly 3 steps" in text
    assert len(text) > 3000   # well over the 512-token minimum for caching


def report(**over) -> "object":
    from agent.brief import Card, CoachReport
    cards = [Card(moment=m, title=t, lines=["look", "why"], callouts=["KNEE 157°"])
             for m, t in zip(["preparation", "contact", "finish"], ["SIT LOWER", "MEET FRONT", "END HIGH"])]
    fields = dict(summary="Your knees are 157°.", headline="Sit low, end high", stroke_type="forehand_topspin",
                  grip="g", stance="s", swing_path="p", contact_point="c", follow_through="f", cards=cards,
                  recap="Sit low, meet front, end high.", drill="Shadow 20.")
    return CoachReport(**{**fields, **over})


def test_one_structured_call_writes_the_coaching_and_is_timed():
    import timing
    from agent import brief
    sent = {}
    msg = SimpleNamespace(stop_reason="end_turn", parsed_output=report(), model="claude-sonnet-5-5",
                          usage=SimpleNamespace(input_tokens=2600, output_tokens=1100, cache_creation_input_tokens=0,
                                                cache_read_input_tokens=3477))
    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(
        parse=lambda **kw: sent.update(kw) or msg)))
    t = timing.start()
    out, model = brief.write("fix my forehand", {"at_contact": {"knee_angle_deg": 157}},
                             [("contact", np.zeros((90, 160, 3), np.uint8))], client=client)
    assert out.cards[0].title == "SIT LOWER" and model == "claude-sonnet-5-5"
    assert sent["model"] == brief.MODEL and sent["output_format"] is brief.CoachReport
    assert sent["system"] == brief.system_blocks() and sent["fallbacks"] == "default"
    images = [c for c in sent["messages"][0]["content"] if c["type"] == "image"]
    assert len(images) == 1 and "157" in sent["messages"][0]["content"][0]["text"]
    row = t.summary()["rows"][0]
    assert row["stage"] == "coach call" and row["cache_read"] == 3477 and row["cost"] > 0
    msg.stop_reason, msg.parsed_output = "refusal", None
    with pytest.raises(RuntimeError, match="declined"):
        brief.write("x", {}, [], client=client)


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    """run_fixed with every heavy step replaced; returns (session, calls)."""
    from agent import fixed
    from agent.tools import Session
    from app import cache, jobs
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path / "jobs")
    job = jobs.create("coach", {"request": "show my best rallies and fix my forehand"})
    video = jobs.job_dir(job["id"]) / "input.mp4"
    video.write_bytes(b"video")
    s = Session(job["id"], video=video)
    calls: list[str] = []
    from app.rally import Rally
    rally = Rally(1.0, 5.0, 8, times=np.array([1.0, 2.0, 3.0]))
    monkeypatch.setattr("app.rally.detect_rallies", lambda *a: calls.append("audio") or [rally])
    monkeypatch.setattr("app.floor_bounce.drop_non_play", lambda v, r, min_hits: (calls.append("play check") or r, []))
    monkeypatch.setitem(fixed.TOOLS, "cut_highlights",
                        lambda s: calls.append("reel") or s.add_output("highlights", "Top 1 rally", "highlights.mp4", "4 s"))
    facts = {"stroke": "forehand", "stroke_type": "forehand_topspin", "stroke_label": "Forehand topspin",
             "bat_hand": "right", "bat_hand_how": "user", "key_times_s": [1.2, 1.5, 1.8], "at_contact": {}, "body": {}}
    monkeypatch.setattr(fixed, "analyse_stroke", lambda *a: calls.append("strokes") or (dict(facts), Path("clip"), None))
    monkeypatch.setattr(fixed, "match_pros", lambda *a: calls.append("pros") or {"facts": [{"name": "Ma Long"}]})
    monkeypatch.setattr(fixed, "compile_pros",
                        lambda s, m: calls.append("pros video") or s.add_output("match", "You play like Ma Long", "p.mp4", ""))

    def coach(s_, request, f, clip, track):
        calls.append("coaching")
        assert f["closest_pros"] == [{"name": "Ma Long"}] and f["rallies"]["count"] == 1
        return report()
    monkeypatch.setattr(fixed, "write_coaching", coach)
    monkeypatch.setattr(fixed, "render", lambda s, f, r, c, t: calls.append("render") or s.add_output(
        "breakdown", "Forehand topspin breakdown", "breakdown.mp4", r.headline))
    return s, calls


def test_the_pipeline_makes_every_output_with_one_coaching_call(pipeline):
    from agent.fixed import run_fixed
    from app import jobs
    s, calls = pipeline
    run_fixed(s, "Here's my match, show my best rallies and fix my forehand")
    job = jobs.load(s.job_id)
    assert job["status"] == "done" and job["summary"] == "Your knees are 157°."
    assert calls.count("coaching") == 1 and "render" in calls and "reel" in calls and "pros video" in calls
    assert calls.index("strokes") < calls.index("coaching") < calls.index("render")
    assert sorted(o["kind"] for o in job["outputs"]) == ["breakdown", "highlights", "match"]
    assert all(t["status"] == "completed" for t in job["todos"])
    assert "/facts.json" in [f["name"] for f in job["agentFiles"]]


def test_the_second_run_on_a_video_reuses_its_rallies(pipeline):
    from agent.fixed import run_fixed
    s, calls = pipeline
    run_fixed(s, "fix my forehand")
    first = list(calls)
    calls.clear()
    run_fixed(s, "fix my forehand")
    assert "audio" in first and "play check" in first
    assert "audio" not in calls and "play check" not in calls and calls.count("coaching") == 1


def test_results_appear_as_they_finish(pipeline, monkeypatch):
    """The coaching call doesn't wait for the highlight reel (a warm run once waited 12 s for
    the cut), and the reel still reaches the job when it's done."""
    import threading
    from agent import fixed
    from app import jobs
    s, calls = pipeline
    writing = threading.Event()

    def slow_reel(s_):
        assert writing.wait(5), "the coaching call waited for the reel"
        s_.add_output("highlights", "Top 1 rally", "highlights.mp4", "4 s")
    monkeypatch.setitem(fixed.TOOLS, "cut_highlights", slow_reel)

    def coach(s_, request, f, clip, track):
        writing.set()
        return report()
    monkeypatch.setattr(fixed, "write_coaching", coach)
    fixed.run_fixed(s, "show my best rallies and fix my forehand")
    job = jobs.load(s.job_id)
    assert "highlights" in [o["kind"] for o in job["outputs"]] and job["status"] == "done"


def test_without_a_key_the_offline_cards_are_used(monkeypatch, tmp_path):
    from agent import fixed
    from agent.tools import Session
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(fixed, "_frames_at", lambda clip, times: [])
    monkeypatch.setattr(fixed, "offline_report", lambda f, c, t: report(summary="offline"))
    updates = {}
    s = SimpleNamespace(update=lambda **kw: updates.update(kw))
    out = fixed.write_coaching(s, "fix", {"key_times_s": [1, 2, 3]}, Path("c"), None)
    assert out.summary == "offline" and "no ANTHROPIC_API_KEY" in updates["engineNote"]




def test_a_warm_run_reuses_the_coached_clip_and_its_pose(tmp_path, monkeypatch):
    """The second analysis of a video makes no clip and runs no pose (16.5 s of a warm run)."""
    from agent import fixed
    from agent.tools import Session
    from app import cache, jobs
    from technique import hitpose, media, pose, strokes
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path / "jobs")
    track = PoseTrack(fps=30, width=640, height=360, times=np.arange(72) / 30, lm=np.full((72, 33, 4), .5, np.float32),
                      world=np.zeros((72, 33, 3), np.float32))
    win = hitpose.HitWindow(hit=5.0, track=track, start=4.4, own=True, peak=18)
    monkeypatch.setattr(hitpose, "hit_pose", lambda *a, **k: hitpose.HitPose(windows=[win], probes=[]))
    monkeypatch.setattr(hitpose, "own_stroke", lambda *a: 18)
    monkeypatch.setattr(hitpose, "coached", lambda *a: win)
    monkeypatch.setattr(fixed, "decide_side", lambda hp, hand: ("right", "user"))
    made = []
    monkeypatch.setattr(media, "make_proxy", lambda v, dst, **k: made.append("clip") or Path(dst).write_bytes(b"clip"))
    monkeypatch.setattr(pose, "extract_pose", lambda clip, identity=None: made.append("pose") or track)
    monkeypatch.setattr(pose, "require_player", lambda *a, **k: 1.0)
    monkeypatch.setattr(pose, "player_thumb", lambda *a: None)
    monkeypatch.setattr(pose, "pose_metrics", lambda *a: {})
    monkeypatch.setattr("technique.pipeline.key_moments", lambda *a, **k: ([.5, .6, .7], 18))
    monkeypatch.setattr(strokes, "detect", lambda *a, **k: ("forehand_topspin", {}))
    monkeypatch.setattr("players.body.body_ratios", lambda tr: {})
    from app.rally import Rally
    for _ in range(2):
        job = jobs.create("coach", {})
        video = tmp_path / "v.mp4"
        video.write_bytes(b"one video")
        s = Session(job["id"], video=video, identity="seed")
        monkeypatch.setattr(s, "seed", lambda v: "seed")
        facts, clip, tr = fixed.analyse_stroke(s, video, cache.video_key(video), "forehand",
                                               [Rally(4.0, 6.0, 4, times=np.array([5.0]))])
        assert clip.read_bytes() == b"clip" and tr.lm.shape == track.lm.shape
    assert made == ["clip", "pose"]
