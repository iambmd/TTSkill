"""Finding the players for "tap the player to analyze": grouping, filtering, auto-skip."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from technique.identity import signature_distance
from technique.people import Detection, box_of, group

TEAL = np.r_[np.eye(48)[3], np.eye(48)[40]]      # torso colour 3, shorts colour 40
BLACK = np.r_[np.eye(48)[20], np.eye(48)[40]]    # a different shirt over the same shorts
OLIVE = np.r_[np.eye(48)[9], np.eye(48)[30]]


def det(frame, look, torso, x=.5):
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
    r = people.detect(people.sample_frames(str(SAMPLES / "IMG_8782.MOV"), 6))
    assert len(r["candidates"]) == 2 and r["decisive"]
    near, far = sorted(r["candidates"], key=lambda c: -c["near"])
    assert near["box"][3] - near["box"][1] > far["box"][3] - far["box"][1]   # the user is the bigger one
    assert r["frame"]["image"].startswith("data:image/jpeg;base64,")
