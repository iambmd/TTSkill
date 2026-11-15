"""Find my pro match: body profile, DTW form comparison, bat-hand filtering and ranking,
height from the table, and the compiled video."""
import json

import cv2
import numpy as np
import pytest

from players import body, compile as comp, match, table
from technique.media import encode_frames
from technique.pose import PoseTrack

N, FPS = 60, 30.0


def _track(scale=1.0, elbow_bend=0.0, n=N) -> PoseTrack:
    """Upright player in normalised image coords; the right wrist swings at frame 30."""
    lm = np.zeros((n, 33, 4), np.float32)
    lm[:, :, 3] = 1
    base = {0: (.5, .15), 11: (.45, .3), 12: (.55, .3), 13: (.42, .42), 14: (.58, .42),
            15: (.40, .52), 16: (.60, .52), 23: (.47, .55), 24: (.53, .55), 25: (.46, .72),
            26: (.54, .72), 27: (.44, .9), 28: (.56, .9)}
    for j, (x, y) in base.items():
        lm[:, j, 0], lm[:, j, 1] = .5 + (x - .5) * scale, .5 + (y - .5) * scale
    t = np.arange(n)
    lm[:, 16, 1] -= 0.12 * scale * (1 / (1 + np.exp(-(t - 30) / 2)))
    lm[:, 16, 0] += elbow_bend
    return PoseTrack(fps=FPS, width=1280, height=720, times=t / FPS, lm=lm,
                     world=np.zeros((n, 33, 3), np.float32))


def test_body_ratios_are_scale_free():
    a, b = body.body_ratios(_track(1.0)), body.body_ratios(_track(0.7))
    for k in ("arm_span_to_height", "leg_to_torso", "shoulder_width_to_height", "stance_width_to_shoulders"):
        assert a[k] > 0 and abs(a[k] - b[k]) < 0.02, k


def test_angle_curves_shape():
    c = body.angle_curves(_track(), "right", 30)
    assert all(len(c[j]) == body.CURVE_POINTS for j in body.JOINTS)
    assert 0 < c["contact_index"] < body.CURVE_POINTS - 1


def test_dtw_handles_timing_shifts():
    x = np.sin(np.linspace(0, 3, 40)) * 40 + 100
    shifted = np.sin(np.linspace(-0.3, 2.7, 40)) * 40 + 100
    assert match.dtw(x, x)[0] == 0
    assert match.dtw(x, shifted)[0] < np.mean(np.abs(x - shifted))
    assert match.dtw(x, x + 30)[0] == pytest.approx(30, abs=0.5)


def test_form_notes_point_at_the_biggest_difference():
    user = body.angle_curves(_track(), "right", 30)
    pro = {**user, "elbow": [v - 25 for v in user["elbow"]]}
    f = match.form_compare(user, pro, "Ma Long")
    assert f["notes"] and "elbow" in f["notes"][0] and "straighter" in f["notes"][0] and "Ma Long" in f["notes"][0]
    assert f["score"] < match.form_compare(user, user, "x")["score"] == 100


def _pro(pid, hand, height, curves, **body_kw):
    b = {"arm_span_to_height": .7, "leg_to_torso": 1.8, "shoulder_width_to_height": .2,
         "stance_width_to_shoulders": 2.0, **body_kw}
    return {"id": pid, "name": pid.title(), "bat_hand": hand, "height_cm": height, "body": b,
            "strokes": {"forehand": [{"curves": curves, "breakdown": None}]}}


def test_match_keeps_bat_hand_and_ranks_by_body():
    c = body.angle_curves(_track(), "right", 30)
    pros = [_pro("tall", "right", 185, c), _pro("short", "right", 160, c), _pro("mid", "right", 172, c),
            _pro("lefty", "left", 172, c), _pro("far", "right", 172, c, leg_to_torso=2.4)]
    user = {"arm_span_to_height": .7, "leg_to_torso": 1.8, "shoulder_width_to_height": .2,
            "stance_width_to_shoulders": 2.0, "height_cm": 171}
    res = match.match(user, c, "forehand", "right", pros=pros)
    assert [r["id"] for r in res] == ["mid", "far", "tall"] or [r["id"] for r in res][0] == "mid"
    assert all(r["bat_hand"] == "right" for r in res) and len(res) == 3
    assert res[0]["score"] >= res[1]["score"] >= res[2]["score"]
    assert res[0]["form_score"] == 100


def test_height_counts_only_when_known():
    pro = _pro("p", "right", 190, {})
    user = {**pro["body"]}
    assert match.body_distance(user, pro) == 0
    assert match.body_distance({**user, "height_cm": 170}, pro) > 1


def test_height_from_the_table(tmp_path):
    """A side-on blue table: top edge at y=400 near the player, feet at y=600 -> ~76 cm rise."""
    frame = np.full((720, 1280, 3), 40, np.uint8)
    cv2.fillPoly(frame, [np.array([[200, 400], [1000, 400], [1000, 440], [200, 440]])], (160, 60, 20))
    vid = str(tmp_path / "t.mp4")
    wr = cv2.VideoWriter(vid, cv2.VideoWriter_fourcc(*"mp4v"), 30, (1280, 720))
    for _ in range(10):
        wr.write(frame)
    wr.release()
    lm = np.zeros((10, 33, 4), np.float32)
    lm[:, :, 3] = 1
    lm[:, :, 0], lm[:, :, 1] = 1100 / 1280, 0.5
    lm[:, 0, 1] = 150 / 720                      # nose
    lm[:, 27, 1] = lm[:, 28, 1] = 600 / 720      # ankles
    for j in (11, 12):
        lm[:, j, 1] = 250 / 720
    for j in (23, 24):
        lm[:, j, 1] = 400 / 720
    tr = PoseTrack(fps=30, width=1280, height=720, times=np.arange(10) / 30, lm=lm,
                   world=np.zeros((10, 33, 3), np.float32))
    est = table.estimate_height_cm(vid, tr, samples=4)
    assert est and 170 <= est["height_cm"] <= 192 and "table_height" in est["method"]


def test_compiled_video(tmp_path, monkeypatch):
    monkeypatch.setattr(comp, "DATA", tmp_path)
    clip = tmp_path / "p" / "breakdown.mp4"
    clip.parent.mkdir()
    encode_frames((np.zeros((1920, 1080, 3), np.uint8) for _ in range(15)), clip, 1080, 1920, 30)
    m = [{"name": "Ma Long", "height_cm": 175, "bat_hand": "right", "country": "CHN", "score": 88,
          "breakdown": "p/breakdown.mp4"}]
    out = comp.compile_matches(m, "forehand", tmp_path / "w", tmp_path / "out.mp4")
    assert out and out.stat().st_size > 1000
    assert comp.compile_matches([{**m[0], "breakdown": None}], "forehand", tmp_path / "w2", tmp_path / "o2.mp4") is None


def test_roster_shape():
    d = json.loads(match.ROSTER.read_text())["players"]
    assert len(d) == 12 and sum(p["gender"] == "M" for p in d) == 6
    assert {p["bat_hand"] for p in d} == {"left", "right"}
    assert all(140 <= p["height_cm"] <= 200 and p["height_source"] for p in d)
