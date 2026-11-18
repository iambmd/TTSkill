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


def test_seed_uses_repeated_near_player_instead_of_first_arrival():
    from technique.identity import dominant_appearance
    looks = [BLACK, BLACK, TEAL, TEAL, TEAL, TEAL, TEAL, TEAL]
    np.testing.assert_allclose(dominant_appearance(looks), TEAL)


def test_seed_is_an_observed_medoid_and_rejects_a_tied_vote():
    from technique.identity import dominant_appearance
    looks = [TEAL, np.array([.9, .1, 0]), np.array([.8, .2, 0]), BLACK]
    chosen = dominant_appearance(looks)
    assert any(np.array_equal(chosen, h) for h in looks)
    assert dominant_appearance([TEAL, BLACK, TEAL, BLACK]) is None
    assert dominant_appearance([TEAL]) is None
    assert dominant_appearance([np.zeros(3), np.zeros(3)]) is None


def test_ambiguous_vote_falls_back_to_the_first_frame_instead_of_failing():
    # 720p coaching demo: the user's cluster and a mixed partner cluster tie 7 v 7.
    from technique.identity import choose_seed
    np.testing.assert_allclose(choose_seed([TEAL, BLACK, TEAL, BLACK]), TEAL)
    np.testing.assert_allclose(choose_seed([BLACK, BLACK, TEAL, TEAL, TEAL, TEAL, TEAL, TEAL]), TEAL)
    assert choose_seed([]) is None


def test_table_phantom_is_not_a_person():
    # 720p coaching demo, frame 0: a skeleton on the table base had full visibility and a
    # longer torso than the real player, but a body only 0.87 torsos tall.
    from technique.pose import implausible
    real = person(.16)
    real[:, 1] = np.linspace(.12, .86, 33)          # head to feet
    real[[11, 12], 1], real[[23, 24], 1] = .3, .52
    phantom = person(.49)
    phantom[:, 1] = .7
    phantom[[11, 12], 1], phantom[[23, 24], 1] = .62, .78
    phantom[[11, 23], 0], phantom[[12, 24], 0] = .44, .54
    assert implausible(np.stack([real, phantom]), 1280, 720).tolist() == [False, True]


def _sig(torso: int, legs: int | None) -> np.ndarray:
    t = np.eye(48)[torso]
    return np.r_[t, np.eye(48)[legs] if legs is not None else np.zeros(48)]


def test_thighs_veto_a_different_player_in_the_same_shirt():
    tr = PlayerIdentity(_sig(3, 40))                 # teal shirt, black shorts
    assert tr.select([person(.3)], [_sig(3, 10)], cut=True) is None   # teal shirt, white shorts
    assert tr.select([person(.3)], [_sig(3, None)], cut=True) == 0    # shorts hidden: torso decides
    assert tr.select([person(.3), person(.7)], [_sig(3, 10), _sig(3, 40)]) == 1


def test_motion_predicts_where_the_player_should_be():
    tr = PlayerIdentity(TEAL)
    for x in (.10, .18, .26, .34):                   # moving right by .08 a frame
        assert tr.select([person(x)], [TEAL]) == 0
    # A lone loose match .11 past the last position: too far to be "in place" without motion,
    # right where the player should be with it.
    assert tr.select([person(.45)], [_look(.7)]) == 0
    still = PlayerIdentity(TEAL)
    assert still.select([person(.34)], [TEAL]) == 0
    assert still.select([person(.45)], [_look(.7)]) is None


def test_zoomed_search_only_when_the_selected_player_is_small_or_missing():
    from technique.pose import QUARTERS, RESEARCH_EVERY, zoom_regions
    tr = PlayerIdentity()
    assert zoom_regions(tr, 0) == {}                       # nobody to look for yet
    tr.reference = TEAL
    assert zoom_regions(tr, 2) == {"extra": QUARTERS}      # tapped but not found yet
    tr.last_box, tr.last_torso, tr.missing = (.4, .25, .48, .42), 120, 0
    assert zoom_regions(tr, 7) == {}                       # big and seen: the usual search
    tr.last_torso = 40
    (region,) = zoom_regions(tr, 7)["first"]               # small: a crop around him
    assert region[0] < .4 and region[2] > .48 and region[1] < .25 and region[3] > .42
    tr.missing = 30
    assert zoom_regions(tr, RESEARCH_EVERY * 3) == {"extra": QUARTERS} and zoom_regions(tr, 31) == {}
