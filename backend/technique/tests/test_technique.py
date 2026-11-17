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
    # (whole-body share, height): far player, near player, near but cut off at the waist
    paddle = {"left": 100, "right": 900}
    shares = {79.4: (.44, .28, paddle), 39.4: (.56, .57, paddle), 9.4: (.06, .56, paddle)}
    monkeypatch.setattr(pipeline.audio, "find_rallies", lambda src: rallies)
    monkeypatch.setattr(pipeline, "player_view", lambda src, s, e, ident, path: shares[round(s, 1)])
    win = pipeline.choose_window("v.mp4", 140, 8.0, tmp_path, lambda m: None, identity=np.ones(3))
    assert win["rally"]["start"] == 40 and win["visible"] == .56
    assert win["paddle"] == {"left": 300, "right": 2700}   # summed over every scanned rally
    # Without an identity (or nobody visible anywhere) the loudest rally still wins.
    assert pipeline.choose_window("v.mp4", 140, 8.0, tmp_path, lambda m: None)["rally"]["start"] == 80
    shares.update({79.4: (.1, .3, paddle), 39.4: (.1, .6, paddle)})
    assert pipeline.choose_window("v.mp4", 140, 8.0, tmp_path, lambda m: None, identity=np.ones(3))["rally"]["start"] == 80


def test_no_leg_metrics_when_legs_are_out_of_frame():
    from technique import pose
    from technique.analyze import OfflineAnalyzer
    tr = _fake_track()
    full = pose.pose_metrics(tr, 45, "right")
    assert full["knee_angle_deg"] is not None and full["stance_width_x_shoulders"] is not None
    tr.lm[:, 25:29, 3] = .05   # close camera cuts the player at the waist
    cut = pose.pose_metrics(tr, 45, "right")
    assert cut["knee_angle_deg"] is None and cut["stance_width_x_shoulders"] is None
    assert cut["elbow_angle_deg"] is not None
    assert not pose.whole_body(tr).any() and pose.whole_body(_fake_track()).all()
    b = OfflineAnalyzer().from_video("v.mp4", "forehand", [], {}, [1., 1.5, 2.], contact_metrics=cut)
    assert "deg" not in b.stance and "out of frame" in b.stance


def test_stance_uses_world_points_when_seen_edge_on():
    from technique import pose
    tr = _fake_track()
    tr.lm[:, [11, 12], 0] = .5          # side view: shoulders overlap in the image
    w = np.zeros((len(tr.times), 33, 3), np.float32)
    for j, (x, y) in {11: (-.2, -.5), 12: (.2, -.5), 13: (-.25, -.25), 14: (.25, -.25), 15: (-.25, 0),
                      16: (.25, 0), 23: (-.1, 0), 24: (.1, 0), 25: (-.15, .45), 26: (.15, .45),
                      27: (-.2, .9), 28: (.2, .9)}.items():
        w[:, j, 0], w[:, j, 1] = x, y
    tr.world = w
    m = pose.pose_metrics(tr, 45, "right")
    assert m["stance_width_x_shoulders"] == 1.0   # ankles .4 m apart, shoulders .4 m


def test_unclear_hand_is_asked_for_or_stated_as_an_assumption(tmp_path):
    import cv2
    from technique.pose import NoPlayer, bat_side
    tr = _fake_track(n=30)
    tr.lm[:, 16, 0] = tr.lm[0, 16, 0]   # neither wrist moves: no speed cue
    vid = str(tmp_path / "v.mp4")
    wr = cv2.VideoWriter(vid, cv2.VideoWriter_fourcc(*"mp4v"), 30, (1280, 720))
    for _ in range(30):
        wr.write(np.full((720, 1280, 3), 90, np.uint8))  # no paddle colour either
    wr.release()
    with pytest.raises(NoPlayer):
        bat_side(vid, tr)
    side, how = bat_side(vid, tr, assume="right")
    assert side == "right" and how.startswith("assumed right-handed")
    assert bat_side(vid, tr, "left", assume="right") == ("left", "user")
    # Bat colour pooled over several rallies decides before the assumption (IMG_8782: 1.82x).
    side, how = bat_side(vid, tr, assume="right", pooled={"left": 21602, "right": 12561 // 2})
    assert side == "left" and how.startswith("paddle colour over several rallies")
    assert bat_side(vid, tr, assume="right", pooled={"left": 21602, "right": 12561})[1].startswith("assumed")
    assert bat_side(vid, tr, "right", pooled={"left": 50000, "right": 10})[1] == "user"


def _stance_track(n=120, fps=30.0, knee_bend=True):
    """A player whose legs bend at the knee (ready stance) or stand straight."""
    tr = _fake_track(n=n, fps=fps)
    if knee_bend:
        tr.lm[:, [25, 26], 0] += .06   # knees pushed forward: about 150 deg at the knee
    return tr


def test_strokes_outside_the_rally_or_away_from_a_hit_are_not_coached():
    from technique.pipeline import real_strokes
    tr = _stance_track()
    T = tr.times
    peaks = [15, 45, 75, 105]                     # 0.5, 1.5, 2.5, 3.5 s
    hits = np.array([0.48, 1.0, 1.52, 2.0, 2.3])  # the rally ends at 2.3 s
    assert real_strokes(tr, peaks, hits) == [15, 45]        # 2.5 s is after the last hit
    assert real_strokes(tr, peaks, np.array([])) == peaks   # no audio: nothing to check against
    assert real_strokes(tr, [75, 105], hits) == [75, 105]   # nothing passes: keep, don't fail


def test_standing_up_after_the_point_is_not_a_stroke():
    from technique.pipeline import ready_stance, real_strokes
    bent, straight = _stance_track(), _stance_track(knee_bend=False)
    assert ready_stance(bent, 30) and not ready_stance(straight, 30)
    # Turn-away after the point: straight legs at the second peak only.
    tr = _stance_track()
    tr.lm[70:80, [25, 26], 0] -= .06
    assert real_strokes(tr, [45, 75], np.array([1.5, 2.5])) == [45]
    legs_cut = _stance_track()
    legs_cut.lm[:, 25:29, 3] = .1                 # close camera: legs out of frame everywhere
    assert real_strokes(legs_cut, [45, 75], np.array([1.5, 2.5])) == [45, 75]


def test_pose_summary_reports_only_the_swings_it_is_given():
    from technique import pose
    tr = _fake_track()
    every = pose.summarize(tr, "right")
    only = pose.summarize(tr, "right", peaks=[45])
    assert only["swing_count"] == 1 and len(only["swings"]) == 1
    assert every["swing_count"] >= 1
