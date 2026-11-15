from pathlib import Path

import numpy as np
import pytest

from app.floor_bounce import crouch_fraction, is_crouched


def pose(shoulder: float, hip: float, ankle: float, wrist: float) -> np.ndarray:
    lm = np.full((33, 2), 0.5)
    lm[[11, 12], 1] = shoulder
    lm[[23, 24], 1] = hip
    lm[[27, 28], 1] = ankle
    lm[[15, 16], 1] = wrist
    return lm


STANDING = pose(shoulder=0.35, hip=0.52, ankle=0.75, wrist=0.45)   # ready position, bat up
BOUNCING = pose(shoulder=0.44, hip=0.53, ankle=0.75, wrist=0.61)   # bent over, hand near the floor


def test_bent_over_with_low_hand_is_crouched():
    assert is_crouched(BOUNCING)
    assert not is_crouched(STANDING)


def test_low_hand_while_upright_is_not_crouched():
    # e.g. a low backhand push: hand below the hip but torso up
    assert not is_crouched(pose(shoulder=0.35, hip=0.52, ankle=0.75, wrist=0.6))


def test_crouch_fraction_counts_frames_with_anyone_crouched():
    frames = [[STANDING, BOUNCING], [STANDING], [], [BOUNCING]]
    assert crouch_fraction(frames) == 0.5
    assert crouch_fraction([]) == 0.0


SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "IMG_8782.MOV"


@pytest.mark.skipif(not SAMPLE.exists(), reason="put IMG_8782.MOV in samples/")
def test_drops_pre_serve_floor_bounce_on_sample(tmp_path):
    from app.floor_bounce import drop_floor_bounces
    from app.rally import detect_rallies

    kept, dropped = drop_floor_bounces(SAMPLE, detect_rallies(SAMPLE, tmp_path))
    assert any(r.start < 17 and r.end > 15 for r in dropped)  # Duke bouncing the ball at ~14-16 s
    assert any(r.start < 66 and r.end > 54 for r in kept)     # the longest rally survives
