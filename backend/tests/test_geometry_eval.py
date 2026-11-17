"""Evaluation safeguards for the rejected, opt-out backswing geometry experiment."""
from __future__ import annotations

import numpy as np
import pytest

from eval.geometry import evidence
from technique.pose import PoseTrack


def track(side: str, wing: str) -> PoseTrack:
    world = np.zeros((45, 33, 3))
    world[:, 11] = [-.3, -1, 0]
    world[:, 12] = [.3, -1, 0]
    lateral, front = (1, .1) if wing == 'forehand' else (.1, 1)
    world[:, 16 if side == 'right' else 15] = [lateral * (1 if side == 'right' else -1), -.5, front]
    lm = np.zeros((45, 33, 4))
    lm[:, :, 3] = 1
    return PoseTrack(30, 720, 720, np.arange(45) / 30, lm, world)


@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('wing', ['forehand', 'backhand'])
def test_body_basis_is_independent_of_camera_yaw_and_hand(side, wing):
    sample = track(side, wing)
    assert evidence(sample, side, 30)['wing'] == wing
    angle = 1.2
    rotation = np.array([[np.cos(angle), 0, np.sin(angle)], [0, 1, 0],
                         [-np.sin(angle), 0, np.cos(angle)]])
    sample.world = sample.world @ rotation.T
    assert evidence(sample, side, 30)['wing'] == wing


def test_hidden_backswing_does_not_use_interpolated_wrist():
    sample = track('right', 'backhand')
    sample.lm[20:29, 16, 3] = .1
    assert evidence(sample, 'right', 30)['wing'] is None


def test_missing_world_basis_abstains():
    sample = track('right', 'backhand')
    sample.world[:] = 0
    assert evidence(sample, 'right', 30)['wing'] is None
    sample.world[:] = np.nan
    assert evidence(sample, 'right', 30)['wing'] is None
