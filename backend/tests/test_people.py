"""Finding the players for "tap the player to analyze": grouping, filtering, auto-skip."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from technique.identity import signature_distance
from technique.people import (Detection, box_of, frame_times, group, lying, one_per_person, spread_order)

TEAL = np.r_[np.eye(48)[3], np.eye(48)[40]]      # torso colour 3, shorts colour 40
BLACK = np.r_[np.eye(48)[20], np.eye(48)[40]]    # a different shirt over the same shorts
OLIVE = np.r_[np.eye(48)[9], np.eye(48)[30]]


def det(frame, look, torso, x=.5):
    """A player in a frame: their box shifts a little from frame to frame, as players do."""
    # Box movement ~0.09 box heights (people.STILL is 0.05; real players measured 0.083-0.594).
    return Detection(frame, (x - .05 + .15 * (frame % 3), .2 + .05 * (frame % 2), x + .05 + .15 * (frame % 3) + .06 * (frame % 2), .9),
                     torso, look)


def sitting(frame, look, torso, x=.5):
    """A spectator: the same box in every frame."""
    return Detection(frame, (x - .05, .2, x + .05, .9), torso, look)


def test_same_shorts_do_not_merge_different_shirts():
    assert signature_distance(TEAL, BLACK) > .9
    assert signature_distance(TEAL, TEAL) == 0
    torso_only = np.r_[np.eye(48)[3], np.zeros(48)]   # knees out of frame: compare the torso only
    assert signature_distance(TEAL, torso_only) == 0


def test_one_player_needs_no_question():
    g = group([det(f, TEAL, 120) for f in range(6)], 6)
    assert len(g["players"]) == 1 and g["decisive"] and g["suggested"] == 0


def test_two_players_with_a_clear_nearest_skip_the_picker():
    # IMG_8782: the user is nearest in every frame; the far opponent is seen in half of them.
    ds = [det(f, TEAL, 120, .6) for f in range(6)] + [det(f, OLIVE, 80, .45) for f in (1, 3, 5)]
    g = group(ds, 6)
    assert len(g["players"]) == 2 and g["decisive"] and g["players"][g["suggested"]][0].look is TEAL


def test_players_taking_turns_nearest_ask_which_one_is_you():
    # A montage: the partner is the near player in half of the clips.
    ds = [det(f, TEAL, 120 if f % 2 else 70, .3) for f in range(6)] + [det(f, BLACK, 70 if f % 2 else 120, .7) for f in range(6)]
    g = group(ds, 6)
    assert len(g["players"]) == 2 and not g["decisive"]


def test_passers_by_and_other_courts_are_not_candidates():
    ds = [det(f, TEAL, 120) for f in range(6)]
    ds += [det(2, BLACK, 110, .1)]                    # walks past once
    ds += [det(f, OLIVE, 20, .9) for f in range(6)]   # a player on the next table, tiny
    g = group(ds, 6)
    assert len(g["players"]) == 1


def test_box_covers_the_visible_body_with_a_margin():
    lm = np.zeros((33, 4))
    lm[:, 0], lm[:, 1], lm[:, 3] = np.linspace(.4, .6, 33), np.linspace(.2, .8, 33), 1
    x0, y0, x1, y1 = box_of(lm)
    assert x0 < .4 and x1 > .6 and y0 < .2 and y1 > .8 and 0 <= x0 and y1 <= 1


SAMPLES = Path(__file__).resolve().parents[2] / "samples"


@pytest.mark.skipif(not (SAMPLES / "IMG_8782.MOV").exists(), reason="put IMG_8782.MOV in samples/")
def test_finds_both_players_on_the_wide_match():
    from technique import people
    r = people.detect(people.sample_frames(str(SAMPLES / "IMG_8782.MOV")))
    # 3 before 2026-11-18: a zoomed crop found the user twice in a frame, which split him in two.
    assert len(r["candidates"]) == 2 and r["decisive"]
    near, far = sorted(r["candidates"], key=lambda c: -c["near"])
    assert near["box"][3] - near["box"][1] > far["box"][3] - far["box"][1]   # the user is the bigger one
    assert r["frame"]["image"].startswith("data:image/jpeg;base64,")
    assert r["timing"]["seconds"] < 10   # the picker must not keep the page waiting


def _fake_detector(monkeypatch, delay: float = 0.0):
    """people.detect without MediaPipe: one standing person per frame, each call taking `delay` s."""
    import threading
    import time
    from technique import people, pose
    calls = []

    def candidates(image, landmarker, mp, extra=None, first=None):
        calls.append(extra is not None)
        time.sleep(delay)
        lm = np.zeros((33, 4), np.float32)
        lm[:, 3] = 1
        lm[:, 0] = .3 + .2 * (len(calls) % 3)   # a player moves about between frames (not "still")
        lm[:, 1] = np.linspace(.1, .9, 33)
        lm[[11, 12], 1], lm[[23, 24], 1] = .3, .5
        lm[[25, 26], 1], lm[[27, 28], 1] = .7, .9
        return [lm], [np.zeros((33, 3), np.float32)]
    monkeypatch.setattr(people, "_landmarker", lambda: (None, None))
    monkeypatch.setattr(pose, "_pose_candidates", candidates)
    # Coloured, so the person's colour signature isn't empty and their sightings group.
    frames = [(float(i), np.full((360, 640, 3), (40, 120, 200), np.uint8)) for i in range(6)]
    return people, frames, calls, threading


def test_detection_answers_within_its_budget(monkeypatch):
    people, frames, calls, _ = _fake_detector(monkeypatch, delay=0.2)
    r = people.detect(frames, budget=0.5)
    # Quarters stop after half the budget, frames after all of it (at least 2 frames answered).
    assert 2 <= r["timing"]["frames"] < 6 and r["timing"]["zoomed_frames"] < r["timing"]["frames"]
    assert r["timing"]["seconds"] < 1.5 and len(r["candidates"]) == 1
    assert calls[:r["timing"]["zoomed_frames"]] == [True] * r["timing"]["zoomed_frames"]


def test_detection_stops_when_the_browser_goes_away(monkeypatch):
    people, frames, calls, threading = _fake_detector(monkeypatch)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(people.Cancelled):
        people.detect(frames, cancel=cancel)
    assert calls == []


def test_the_pose_model_is_loaded_once_per_thread():
    from technique import people
    a, _ = people._landmarker()
    b, _ = people._landmarker()
    assert a is b


def test_detection_reports_people_per_frame(monkeypatch):
    people, frames, _, _ = _fake_detector(monkeypatch)
    r = people.detect(frames)
    assert r["frames"] == [{"time": float(i), "people": 1} for i in range(6)]


# ------------------------------------------------------------------ 12 frames over the whole video

def skeleton(x: float, shoulder_y: float = .3, hip_y: float = .5, knee_y: float = .7, ankle_y: float = .9,
             knee_dx: float = 0.0, vis: float = 1.0) -> np.ndarray:
    """A standing person at x (normalised), with joints at the given heights."""
    lm = np.zeros((33, 4), np.float32)
    lm[:, 0], lm[:, 3] = x, vis
    lm[:, 1] = np.linspace(shoulder_y - .1, ankle_y, 33)
    lm[[11, 12], 1], lm[[23, 24], 1] = shoulder_y, hip_y
    lm[[25, 26], 1], lm[[27, 28], 1] = knee_y, ankle_y
    lm[[11, 23, 25, 27], 0] -= .02
    lm[[12, 24, 26, 28], 0] += .02
    lm[[25, 26], 0] += knee_dx
    return lm


def test_two_skeletons_of_one_person_in_a_frame_count_once():
    # IMG_8782 at 161 s: a zoomed quarter re-found the user as a partial body (shoulders 2 px apart).
    whole = skeleton(.5)
    partial = skeleton(.505, hip_y=.45, knee_y=.6, vis=.3)
    far = skeleton(.2, .25, .32, .4, .48)   # the opponent across the table: elsewhere, smaller
    kept = one_per_person([partial, whole, far], 1280, 720)
    assert len(kept) == 2 and any(k is whole for k in kept) and any(k is far for k in kept)


def test_a_skeleton_inside_someone_elses_box_is_that_person():
    legs_only = skeleton(.5, shoulder_y=.62, hip_y=.7, knee_y=.8, ankle_y=.88, vis=.6)
    assert len(one_per_person([skeleton(.5), legs_only], 1280, 720)) == 1


def test_a_body_traced_over_the_table_legs_is_not_a_person():
    assert not lying(skeleton(.5), 1280, 720)                                   # standing
    assert lying(skeleton(.5, knee_y=.5, knee_dx=-.2), 1280, 720)              # thighs flat along a table leg
    assert not lying(skeleton(.5, knee_y=.52, knee_dx=-.03), 1280, 720)        # a squashed fit on a real person


def test_a_player_who_comes_into_shot_late_is_still_a_candidate():
    ds = [det(f, TEAL, 120, .3) for f in range(12)]
    ds += [det(f, BLACK, 90, .7) for f in (9, 10, 11)]   # walks in for the last quarter of the video
    ds += [det(4, OLIVE, 100, .5)]                       # a passer-by, once
    g = group(ds, 12)
    assert [pl[0].look is BLACK for pl in g["players"]] == [False, True]


def test_one_person_split_by_the_greedy_pass_is_joined_again():
    near_teal = np.r_[np.eye(48)[3] * .9 + np.eye(48)[4] * .1, np.eye(48)[40]]
    ds = [det(f, TEAL, 120) for f in range(3)] + [det(f, near_teal, 118) for f in range(3, 6)]
    ds += [det(f, BLACK, 90, .2) for f in range(6)]
    assert len(group(ds, 6)["players"]) == 2


def test_frames_are_looked_at_start_middle_and_end_first():
    order = spread_order(12)
    assert sorted(order) == list(range(12))
    assert order[0] == 0 and order[1] == 6 and {order[2], order[3]} == {3, 9}


def test_a_budget_cut_still_covers_the_whole_video(monkeypatch):
    people, _, _, _ = _fake_detector(monkeypatch, delay=0.1)
    frames = [(float(t), np.full((360, 640, 3), 120, np.uint8)) for t in range(0, 120, 10)]
    r = people.detect(frames, budget=0.25)
    times = [f["time"] for f in r["frames"]]
    assert 2 <= len(times) < 12 and min(times) < 30 and max(times) >= 60   # not just the first frames


def test_frame_times_prefer_the_rallies_and_reach_the_end():
    times = frame_times(200.0, [(20.0, 30.0), (150.0, 170.0)])
    inside = [t for t in times if 20 <= t <= 30 or 150 <= t <= 170]
    assert len(times) == 12 and len(inside) >= 9 and max(times) > 150
    assert frame_times(60.0, []) == [round((i + .5) / 12 * 60, 3) for i in range(12)]   # no rallies: even


def test_sample_frames_reads_any_video_with_ffmpeg(media):
    from technique import people
    frames = people.sample_frames(str(media["ok"]))
    assert len(frames) == 12 and frames[0][1].shape == (360, 640, 3)
    assert frames[0][0] < .3 and frames[-1][0] > 2.7   # spread over the whole 3 s


@pytest.fixture(scope="module")
def late_entry(tmp_path_factory) -> Path:
    """40 s of IMG_8782 whose first 30 s are black and silent: the players are only in the last 10 s."""
    import subprocess
    out = tmp_path_factory.mktemp("late") / "late.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-ss", "110", "-t", "40", "-i", str(SAMPLES / "IMG_8782.MOV"),
                    "-vf", "scale=-2:360,drawbox=enable='lt(t,30)':color=black:t=fill",
                    "-af", "volume=enable='lt(t,30)':volume=0", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(out)], check=True)
    return out


@pytest.mark.skipif(not (SAMPLES / "IMG_8782.MOV").exists(), reason="put IMG_8782.MOV in samples/")
def test_finds_a_player_who_is_only_in_the_last_quarter(late_entry):
    from technique import people
    even = [(t, people.grab_frame(str(late_entry), t)) for t in frame_times(40.0, [])]   # as the browser draws them
    for frames in (even, people.sample_frames(str(late_entry))):
        r = people.detect(frames)
        assert r["candidates"], "the late player was dropped"
        assert all(c["time"] >= 30 for c in r["candidates"])
        assert r["frame"]["time"] >= 30



# ------------------------------------------------------------------ background people, "Only me"

moving = det


def test_people_who_barely_move_are_background_not_players():
    ds = [moving(f, TEAL, 120, .5) for f in range(12)]
    ds += [sitting(f, OLIVE, 100, .85) for f in (2, 5, 8, 11)]   # a spectator on a bench: the same box every time
    g = group(ds, 12)
    assert len(g["players"]) == 1 and [why for _, why in g["others"]] == ["still"]


def test_people_far_from_the_table_are_background():
    table = (.35, .45, .65, .6)   # 0.3 wide
    ds = [moving(f, TEAL, 120, .3) for f in range(6)] + [moving(f, BLACK, 90, .7) for f in range(6)]
    ds += [moving(f, OLIVE, 100, -.25) for f in range(6)]   # at least 0.19 (0.6 table widths) off the table's side
    g = group(ds, 6, [table] * 6)
    assert len(g["players"]) == 2 and [why for _, why in g["others"]] == ["far"]
    # A "table" everyone is far from (a blue banner, say) rules nobody out.
    assert len(group(ds, 6, [(1.5, .0, 1.6, .05)] * 6)["players"]) == 3


def test_a_still_spectator_near_the_camera_does_not_make_the_players_small():
    ds = [moving(f, TEAL, 60, .3) for f in range(6)] + [moving(f, BLACK, 50, .6) for f in range(6)]
    ds += [sitting(f, OLIVE, 250, .9) for f in range(6)]   # big and motionless, right by the phone
    g = group(ds, 6)
    assert len(g["players"]) == 2 and [why for _, why in g["others"]] == ["still"]


def _fake_video(monkeypatch, people_at):
    """most_active without a video or MediaPipe: people_at(t) -> skeletons at time t."""
    from technique import audio, media, people, pose
    monkeypatch.setattr(media, "probe", lambda v: {"duration": 20.0})
    monkeypatch.setattr(audio, "find_rallies", lambda v: [])
    monkeypatch.setattr(people, "grab_frame", lambda v, t: np.full((360, 640, 3), int(t * 10) % 255, np.uint8))
    monkeypatch.setattr(people, "_landmarker", lambda: (None, None))
    monkeypatch.setattr(people, "_table_box", lambda im: None)
    looks = {}

    def candidates(image, landmarker, mp, extra=None, first=None):
        t = image[0, 0, 0] / 10
        found = people_at(t)
        return found, [np.zeros((33, 3), np.float32) for _ in found]

    def sig(image, p):
        return looks[round(float(p[0, 0]), 1)]
    monkeypatch.setattr(pose, "_pose_candidates", candidates)
    monkeypatch.setattr(people, "signature", sig)
    return people, looks


def swinging(x: float, t: float, scale: float = 1.0, amount: float = .1) -> np.ndarray:
    """A player at x whose arms swing: the wrists move with time."""
    p = skeleton(x, .5 - .2 * scale, .5, .5 + .2 * scale, .5 + .4 * scale)
    p[[13, 14, 15, 16], 0] += amount * np.sin(t * 15)
    p[0, 0] = x   # the fake signature is keyed on this
    return p


def test_only_me_follows_whoever_plays_the_most(monkeypatch):
    def at(t):
        bench = skeleton(.9)                   # sits still the whole video, nearest the camera
        bench[0, 0] = .9
        return [swinging(.3, t, .8), bench]
    people, looks = _fake_video(monkeypatch, at)
    looks.update({.3: TEAL, .9: OLIVE})
    assert people.most_active("v.mp4") is TEAL


def test_only_me_prefers_the_near_player_over_a_jittery_far_one(monkeypatch):
    def at(t):
        return [swinging(.3, t, 1.0, .08), swinging(.7, t, .4, .06)]   # far: small, landmarks jump
    people, looks = _fake_video(monkeypatch, at)
    looks.update({.3: TEAL, .7: BLACK})
    assert people.most_active("v.mp4") is TEAL


def test_coach_seeds_from_whoever_plays_the_most_with_only_me(monkeypatch):
    from agent.tools import Session
    from technique import people, pose
    monkeypatch.setattr(people, "most_active", lambda v: "active")
    monkeypatch.setattr(pose, "initial_identity", lambda v: "nearest")
    assert Session("j", only_me=True).seed(Path("v.mp4")) == "active"
    assert Session("j").seed(Path("v.mp4")) == "nearest"
    monkeypatch.setattr(people, "most_active", lambda v: None)   # nobody seen: the usual seed
    assert Session("j", only_me=True).seed(Path("v.mp4")) == "nearest"


@pytest.fixture(scope="module")
def alone(tmp_path_factory) -> Path:
    """30 s of IMG_8782 cropped to its right side: the user alone, the opponent cut out."""
    import subprocess
    out = tmp_path_factory.mktemp("alone") / "alone.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-ss", "95", "-t", "30", "-i", str(SAMPLES / "IMG_8782.MOV"),
                    "-vf", "crop=iw*0.56:ih:iw*0.44:0,scale=-2:540", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(out)], check=True)
    return out


@pytest.mark.skipif(not (SAMPLES / "IMG_8782.MOV").exists(), reason="put IMG_8782.MOV in samples/")
def test_one_person_in_the_video_is_one_candidate(alone):
    from technique import people
    r = people.detect(people.sample_frames(str(alone)))
    assert len(r["candidates"]) == 1 and r["candidates"][0]["seen"] >= .75


def test_nobody_in_the_video_is_no_candidate(media):
    from technique import people
    r = people.detect(people.sample_frames(str(media["ok"])))   # a test pattern
    assert r["candidates"] == [] and r["others"] == [] and r["frame"] is None
    assert [f["people"] for f in r["frames"]] == [0] * 12
