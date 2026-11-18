"""Pose at the strokes (technique/hitpose.py) and the per-video cache (app/cache.py)."""
from __future__ import annotations

import numpy as np

from technique import hitpose
from technique.pose import PoseTrack


def standing(n: int, x: float = .5, height: float = .6, wrist_dx=None, fps: float = 30.0) -> PoseTrack:
    """A standing player for n frames; the right wrist moves by wrist_dx[i] (frame share)."""
    lm = np.zeros((n, 33, 4), np.float32)
    top = .5 - height / 2
    lm[:, :, 0], lm[:, :, 3] = x, 1.0
    lm[:, :, 1] = np.linspace(top, top + height, 33)
    lm[:, [11, 12], 1], lm[:, [23, 24], 1] = top + .2 * height, top + .5 * height
    lm[:, [25, 26], 1], lm[:, [27, 28], 1] = top + .75 * height, top + height
    lm[:, [11, 13, 15, 23, 25, 27], 0] -= .03
    lm[:, [12, 14, 16, 24, 26, 28], 0] += .03
    if wrist_dx is not None:
        lm[:, 16, 0] += np.asarray(wrist_dx, np.float32)
    return PoseTrack(fps=fps, width=1280, height=720, times=np.arange(n) / fps, lm=lm,
                     world=np.zeros((n, 33, 3), np.float32), meta={"stride": 1})


def test_close_onsets_are_one_stroke():
    assert hitpose.strokes_only([1.0, 1.13, 1.5, 1.6, 2.4]) == [1.0, 1.5, 2.4]


def test_the_probe_reads_how_fast_each_wrist_moves_at_an_onset():
    frames = []
    for dx in (0.0, .08, .16):   # the right wrist sweeps 0.08 of the frame per 0.1 s
        t = standing(1).lm[0].copy()
        t[16, 0] += dx
        frames.append(t)
    sp = hitpose.probe_speeds(frames, 1280, 720)
    assert sp["left"] == 0 and sp["right"] > hitpose.STROKE_SPEED


def test_only_a_fast_bat_wrist_at_the_sound_is_the_players_own_stroke():
    n = 36
    swing = np.zeros(n)
    swing[16:21] = np.cumsum([.04, .06, .08, .06, .04])   # a swing peaking at frame ~18 (0.6 s)
    swing[21:] = swing[20]
    own = standing(n, wrist_dx=swing)
    assert hitpose.own_stroke(own, 0.6, "right") is not None
    ready = standing(n, wrist_dx=np.linspace(0, .02, n))   # the opponent hits: the wrist drifts
    assert hitpose.own_stroke(ready, 0.6, "right") is None


def window(hit: float, track: PoseTrack, peak: int = 18) -> hitpose.HitWindow:
    return hitpose.HitWindow(hit=hit, track=track, start=hit - .6, own=True, peak=peak)


def test_the_coached_stroke_is_seen_whole_and_big_not_just_fast(monkeypatch):
    fast = np.zeros(36)
    fast[16:21] = np.cumsum([.05, .08, .1, .08, .05])
    fast[21:] = fast[20]
    moderate = fast * .6
    far = window(30.8, standing(36, x=.67, height=.21, wrist_dx=fast))      # the montage's far figure
    cut = window(50.9, standing(36, x=.02, height=.58, wrist_dx=fast))      # touching the frame edge
    good = window(56.4, standing(36, x=.3, height=.59, wrist_dx=moderate))
    hp = hitpose.HitPose(windows=[far, cut, good])
    monkeypatch.setattr("technique.pipeline.ready_stance", lambda tr, i: True)
    assert hitpose.coached(hp, "right") is good
    assert hitpose.view(cut.track)["inside"] < .8 and hitpose.view(far.track)["height"] < .25


def test_the_cache_keeps_a_videos_analysis(tmp_path, monkeypatch):
    from app import cache, jobs
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path / "jobs")
    video = tmp_path / "v.mp4"
    video.write_bytes(b"same bytes")
    key = cache.video_key(video)
    calls = []
    first = cache.cached(key, "rallies", lambda: calls.append(1) or [1, 2, 3])
    again = cache.cached(key, "rallies", lambda: calls.append(1) or [9])
    assert first == ([1, 2, 3], False) and again == ([1, 2, 3], True) and calls == [1]
    path = next((tmp_path / "cache" / key).glob("rallies.*"))
    path.write_bytes(b"not a pickle")   # a broken entry is computed again
    assert cache.cached(key, "rallies", lambda: [4]) == ([4], False)
    other = tmp_path / "w.mp4"
    other.write_bytes(b"other bytes")
    assert cache.video_key(other) != key


