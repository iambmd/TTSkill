"""Identity continuity with side switches, occlusion, cuts, and similar clothing."""
from __future__ import annotations

import numpy as np

from technique.identity import PlayerIdentity


def person(x: float, size: float = .2) -> np.ndarray:
    p = np.zeros((33, 4))
    p[:, 0], p[:, 1], p[:, 3] = x, .6, 1
    p[[11, 12], 1] -= size
    return p


TEAL, BLACK = np.array([1., 0., 0.]), np.array([0., 1., 0.])


def test_identity_survives_side_switch_and_cut():
    tr = PlayerIdentity()
    assert tr.select([person(.2), person(.8, .1)], [TEAL, BLACK]) == 0
    assert tr.select([person(.2, .2), person(.8, .1)], [BLACK, TEAL], cut=True) == 1
    assert tr.select([], []) is None
    assert tr.select([person(.8)], [BLACK]) is None
    assert tr.select([person(.1), person(.9)], [BLACK, TEAL]) == 1


def test_ambiguous_reidentification_abstains():
    tr = PlayerIdentity(TEAL)
    assert tr.select([person(.2), person(.8)], [TEAL, TEAL], cut=True) is None


def test_window_seed_does_not_select_bigger_opponent():
    tr = PlayerIdentity(TEAL)
    assert tr.select([person(.2, .3), person(.8, .1)], [BLACK, TEAL]) == 1


def test_contact_hand_ignores_free_arm_motion_away_from_contacts():
    from technique.pose import contact_side
    from technique.tests.test_strokes import _track, _sweep
    tr = _track(lambda t: np.full_like(t, .62), _sweep(.62, .42))
    # Left wrist moves strongly before the contact window, then stays still.
    tr.lm[:15, 15, 0] = np.linspace(0, 2, 15)
    tr.lm[15:, 15, 0] = 2
    assert contact_side(tr, [1.45, 1.55]) == 'right'
    tr.lm[:, 16, 3] = .1
    assert contact_side(tr, [1.45, 1.55]) == 'unknown'


def test_torso_colour_match_tolerates_nearby_lighting_bins():
    import cv2
    from technique.identity import appearance
    p = person(.5)
    p[[11,23],0], p[[12,24],0] = .3, .7
    hsv_a = np.full((100,100,3), (88, 120, 150), np.uint8)
    hsv_b = np.full((100,100,3), (92, 120, 190), np.uint8)
    a = appearance(cv2.cvtColor(hsv_a, cv2.COLOR_HSV2BGR), p)
    b = appearance(cv2.cvtColor(hsv_b, cv2.COLOR_HSV2BGR), p)
    tracker = PlayerIdentity(a)
    assert tracker.select([p], [b], cut=True) == 0


def _look(distance: float) -> np.ndarray:
    """A histogram at a chosen colour distance from TEAL (distance = sqrt(1 - sqrt(a)))."""
    a = (1 - distance ** 2) ** 2
    return np.array([a, 1 - a, 0.])


def test_loose_match_accepted_when_clearly_closest_in_frame():
    # Lighting changed: the player scores .7, the opponent 1.0. Abstaining here starved Coach.
    tr = PlayerIdentity(TEAL)
    assert tr.select([person(.2), person(.8)], [_look(.7), BLACK]) == 0


def test_loose_match_rejected_when_another_person_is_close():
    tr = PlayerIdentity(TEAL)
    assert tr.select([person(.2), person(.8)], [_look(.7), _look(.8)]) is None


def test_lone_loose_match_needs_continuity():
    tr = PlayerIdentity(TEAL)
    assert tr.select([person(.2)], [_look(.7)], cut=True) is None
    assert tr.select([person(.2)], [_look(.3)]) == 0
    assert tr.select([person(.21)], [_look(.7)]) == 0      # same place, next frame
    assert tr.select([person(.8)], [_look(.7)]) is None     # somebody else, elsewhere
    assert tr.select([person(.2)], [_look(.7)], cut=True) is None
