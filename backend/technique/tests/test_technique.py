"""Fast tests (no network, no model download). Run: cd backend && pytest technique/tests"""
import json
import os
from pathlib import Path

import numpy as np
import pytest

from technique import audio
from technique.analyze import OfflineAnalyzer, normalize_stroke
from technique.pipeline import key_moments
from technique.pose import PoseTrack
from technique.render import render_text_only
from technique.schema import STROKES, StrokeBreakdown
from technique.video_prompt import build_prompts, generate_video

SAMPLE = os.environ.get("TTSKILL_SAMPLE", "/mnt/project-files/IMG_8782.MOV")


def _fake_track(n=90, fps=30.0, swing_at=45):
    lm = np.zeros((n, 33, 4), np.float32)
    lm[:, :, 3] = 1
    base = {0: (.5, .2), 11: (.45, .3), 12: (.55, .3), 13: (.42, .4), 14: (.58, .4),
            15: (.40, .5), 16: (.60, .5), 23: (.47, .55), 24: (.53, .55), 25: (.46, .7),
            26: (.54, .7), 27: (.45, .9), 28: (.55, .9)}
    for j, (x, y) in base.items():
        lm[:, j, 0], lm[:, j, 1] = x, y
    t = np.arange(n)
    # right wrist swings fast around `swing_at`
    lm[:, 16, 0] += 0.15 * np.exp(-((t - swing_at) / 4.0) ** 2) * np.sign(t - swing_at)
    return PoseTrack(fps=fps, width=1280, height=720, times=t / fps, lm=lm,
                     world=np.zeros((n, 33, 3), np.float32))


def test_group_rallies():
    hits = np.array([1.0, 1.5, 2.0, 2.6, 10.0, 10.4, 30.0, 30.5, 31.0, 31.4, 31.9])
    r = audio.group_rallies(hits, gap=1.6, min_hits=4)
    assert [x["hits"] for x in r] == [4, 5]


def test_key_moments_prefers_swing_on_hit():
    tr = _fake_track()
    keys, i = key_moments(tr, "right", hit_times=[1.5])
    assert abs(keys[1] - 1.5) < 0.2
    assert keys[0] < keys[1] < keys[2]


@pytest.mark.parametrize("stroke", STROKES)
def test_offline_breakdown_and_prompt(stroke):
    b = OfflineAnalyzer().from_video("x.mp4", stroke, [], {"bat_hand": "right"}, [0.5, 1.0, 1.5],
                                     contact_metrics={"knee_angle_deg": 130, "elbow_angle_deg": 110,
                                                      "stance_width_x_shoulders": 1.8,
                                                      "wrist_height_hip0_shoulder1": 0.5})
    assert len(b.steps) == 3 and all(len(s.lines) == 2 for s in b.steps)
    assert "deep knee bend" in b.stance
    p = build_prompts(b)
    assert len(p["prompt"]) <= 512 and stroke in p["prompt"]
    assert len(p["shots"]) == 3
    StrokeBreakdown.model_validate_json(b.model_dump_json())


def test_no_paid_video_provider_by_default(tmp_path):
    b = OfflineAnalyzer().from_text("x", "serve")
    assert generate_video(build_prompts(b), str(tmp_path / "g.mp4")) is None
    with pytest.raises(NotImplementedError):
        generate_video(build_prompts(b), str(tmp_path / "g.mp4"), provider="veo")


def test_normalize_stroke():
    assert normalize_stroke("Backhand ") == "backhand"
    assert normalize_stroke("smash") == "forehand"


def test_text_only_render(tmp_path):
    b = OfflineAnalyzer().from_text("loops with a big waist turn", "forehand", "Ma Long")
    out = render_text_only(b, str(tmp_path / "t.mp4"))
    assert Path(out).stat().st_size > 10_000


@pytest.mark.skipif(not Path(SAMPLE).exists(), reason="sample video not available")
def test_sample_longest_rally_found():
    r = audio.find_rallies(SAMPLE)
    best = max(r, key=lambda x: x["hits"])
    assert best["start"] < 60 < best["end"]


def test_bat_side_uses_paddle_colour_then_user_hand(tmp_path):
    import cv2
    from technique.pose import bat_side
    tr = _fake_track(n=30)
    vid = str(tmp_path / "v.mp4")
    wr = cv2.VideoWriter(vid, cv2.VideoWriter_fourcc(*"mp4v"), 30, (1280, 720))
    for _ in range(30):
        wr.write(np.full((720, 1280, 3), 90, np.uint8))  # grey: no paddle visible
    wr.release()
    assert bat_side(vid, tr, "left") == ("left", "user")
    # paint a red paddle at the left-wrist position (x=0.40, y=0.50)
    wr = cv2.VideoWriter(vid, cv2.VideoWriter_fourcc(*"mp4v"), 30, (1280, 720))
    for _ in range(30):
        f = np.full((720, 1280, 3), 90, np.uint8)
        cv2.circle(f, (512, 360), 40, (0, 0, 220), -1)
        wr.write(f)
    wr.release()
    side, how = bat_side(vid, tr, "right")
    assert side == "left" and how.startswith("paddle")
    # a known bat hand (roster pro) beats the paddle colour
    assert bat_side(vid, tr, "right", trust_hand=True) == ("right", "known")


def test_window_prefers_busy_rally_where_the_player_is_visible(tmp_path, monkeypatch):
    from technique import pipeline
    rallies = [{"start": 80, "end": 88, "hits": 26, "hit_times": [81.]},   # user is the far player
               {"start": 40, "end": 47, "hits": 20, "hit_times": [41.]},
               {"start": 10, "end": 15, "hits": 12, "hit_times": [11.]}]
    shares = {79.4: .2, 39.4: .8, 9.4: .9}
    monkeypatch.setattr(pipeline.audio, "find_rallies", lambda src: rallies)
    monkeypatch.setattr(pipeline, "visible_share", lambda src, s, e, ident, path: shares[round(s, 1)])
    win = pipeline.choose_window("v.mp4", 140, 8.0, tmp_path, lambda m: None, identity=np.ones(3))
    assert win["rally"]["start"] == 40 and win["visible"] == .8
    # Without an identity (or nobody visible anywhere) the loudest rally still wins.
    assert pipeline.choose_window("v.mp4", 140, 8.0, tmp_path, lambda m: None)["rally"]["start"] == 80
    shares.update({39.4: .1, 9.4: .1})
    assert pipeline.choose_window("v.mp4", 140, 8.0, tmp_path, lambda m: None, identity=np.ones(3))["rally"]["start"] == 80
