"""Crossfade joins and clip-aware regrouping, on synthetic frames and rallies."""
from __future__ import annotations

import numpy as np

from app import clips
from app.rally import Rally


def _scene(seed: int, n: int = 30, x0: int = 20, y0: int = 30) -> np.ndarray:
    """A fixed background with one bright square (a player) drifting across it."""
    rng = np.random.default_rng(seed)
    bg = rng.uniform(.2, .6, (90, 160)).astype(np.float32)
    f = np.repeat(bg[None], n, axis=0)
    for i in range(n):
        x = x0 + 3 * i
        f[i, y0:y0 + 30, x:x + 12] = .95
    return f


def test_motion_alone_is_not_a_join():
    assert clips.find_joins(_scene(1, 60)) == []


def test_crossfade_between_two_trims_of_one_camera_is_a_join():
    # Same background, players in different places: what a scene-cut detector can't see.
    a, b = _scene(1, 30), _scene(1, 30, x0=50, y0=5)
    ramp = np.linspace(0, 1, 7)[1:-1, None, None]
    fade = a[-1] * (1 - ramp) + b[0] * ramp
    joins = clips.find_joins(np.concatenate([a, fade, b]), t0=10.0)
    assert len(joins) == 1 and abs(joins[0] - (10.0 + 32 / clips.FPS)) < .3


def test_hard_cut_is_not_reported_as_a_crossfade():
    # Known gap: a hard cut from the same camera needs another detector (see HANDOFF.md).
    assert clips.find_joins(np.concatenate([_scene(1, 30), _scene(1, 30, x0=50, y0=5)])) == []


def _rally(*times: float) -> Rally:
    t = np.array(times)
    return Rally(float(t[0]), float(t[-1]), len(t), t)


def test_regroup_splits_at_joins_and_merges_within_a_clip():
    spanning = _rally(1, 1.5, 2, 2.5, 3, 5.5, 6, 6.5, 7)       # straddles the join at 4.2
    later = _rally(9.5, 10, 10.5, 11)                            # same clip as 5.5-7, 2.5 s later
    out = clips.regroup([spanning, later], joins=[4.2, 20.0])
    assert [(r.start, r.end, r.hits) for r in out] == [(1, 3, 5), (5.5, 11, 8)]


def test_regroup_never_merges_across_a_join_or_a_long_gap():
    out = clips.regroup([_rally(1, 2, 3, 4), _rally(5, 6, 7, 8), _rally(14, 15, 16, 17)], joins=[4.5])
    assert [(r.start, r.end) for r in out] == [(1, 4), (5, 8), (14, 17)]


def test_regroup_drops_fragments_and_leaves_continuous_video_alone():
    assert clips.regroup([_rally(1, 2, 3, 3.9, 4.5)], joins=[4.2]) == [_rally(1, 2, 3, 3.9)]
    rallies = [_rally(1, 2, 3, 4), _rally(5, 6, 7, 8)]
    assert clips.regroup(rallies, joins=[]) is rallies


def test_joins_seen_from_two_windows_count_once():
    assert clips.merge_joins([33.1, 33.4, 60.9]) == [33.25, 60.9]
    assert [clips.clip_index(t, [33.25, 60.9]) for t in (5, 40, 61)] == [0, 1, 2]


def test_contact_exactly_at_join_belongs_to_next_clip():
    out = clips.regroup([_rally(1, 2, 3, 4, 5, 6)], [4], min_hits=3)
    assert [(r.start, r.end, r.hits) for r in out] == [(1, 3, 3), (4, 6, 3)]
    assert out[0].clip_bounds == (0, 4)
    assert out[1].clip_bounds == (4, np.inf)


def test_custom_min_hits_applies_after_regrouping():
    out = clips.regroup([_rally(1, 2, 3, 5, 6, 7, 8, 9)], [4], min_hits=5)
    assert [(r.start, r.end, r.hits) for r in out] == [(5, 9, 5)]


def test_montage_crossfade_breaks_the_reported_27_to_50_second_merge():
    from pathlib import Path
    import pytest
    from app.floor_bounce import _frames
    sample = Path(__file__).resolve().parents[2] / "samples" / "coaching-demo.mp4"
    if not sample.exists():
        pytest.skip("put coaching-demo.mp4 in samples/")
    joins = clips.find_joins(clips.gray(_frames(sample, 26, 51)), 26)
    # Three joins separate the four clips in this previously merged candidate.
    for start, end in ((33, 35), (37, 40), (43, 45)):
        assert any(start <= j <= end for j in joins), joins
    out = clips.regroup([_rally(*np.arange(27.4, 50.1, .3))], joins)
    assert len(out) == 4
    assert not any(r.start < j < r.end for r in out for j in joins)


def test_non_play_candidate_cannot_bridge_rallies_through_short_gaps():
    first = _rally(107, 108, 109, 110, 111, 112)
    retrieval = _rally(114, 115, 116, 117)
    second = _rally(120, 121, 122, 123)
    # All adjacent gaps are below MERGE_GAP, but the whole break is eight seconds.
    out = clips.regroup([first, retrieval, second], [106, 130], non_play=[(114, 117)])
    assert [(r.start, r.end) for r in out] == [(107, 112), (114, 117), (120, 123)]
