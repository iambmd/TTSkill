"""Temporal classification preserves order and abstains on ambiguous evidence."""
from __future__ import annotations

import numpy as np

from technique.temporal import distance, predict, sequence
from technique.tests.test_strokes import _track, _sweep


def test_same_swing_at_different_speed_matches_better_than_reverse():
    t = np.linspace(0, 1, 21)
    a = np.column_stack([t, t*t])
    b = np.column_stack([t**1.2, t**2.4])
    assert distance(a, b) < distance(a, a[::-1])


def test_left_and_right_hand_sequences_share_coordinates():
    tr = _track(lambda t: np.full_like(t, .62), _sweep(.62, .42))
    right = sequence(tr, 'right', 45)
    tr.lm[:, :, 0] = 1 - tr.lm[:, :, 0]
    for a, b in [(11,12), (13,14), (15,16), (23,24)]:
        tr.lm[:, [a,b]] = tr.lm[:, [b,a]]
    np.testing.assert_allclose(sequence(tr, 'left', 45), right, atol=1e-5)


def test_tied_or_missing_classes_do_not_override_heuristic():
    q = np.zeros((21,4))
    assert predict(q, [])[0] is None
    templates = [{'wing': wing, 'sequence': q.tolist()} for wing in ('forehand','backhand') for _ in range(3)]
    assert predict(q, templates)[0] is None
