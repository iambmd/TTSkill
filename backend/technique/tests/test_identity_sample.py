"""The original match must select the player who enters after the opening frames."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from technique import media, pose

ROOT = Path(__file__).resolve().parents[3]
LABELS = ROOT / 'backend/eval/regressions/img8782_identity.json'


def test_late_arriving_player_seeds_the_analysis_window(tmp_path):
    labels = json.loads(LABELS.read_text())
    sample = ROOT / labels['video']
    if not sample.exists():
        pytest.skip('put IMG_8782.MOV in samples/')
    reference = pose.initial_identity(sample)
    assert reference is not None
    clip = media.make_proxy(sample, tmp_path / 'clip.mp4', height=720, fps=30, start=24, end=26)
    track = pose.extract_pose(clip, stride=5, identity=reference)
    pose.require_player(track)
    label = next(row for row in labels['frames'] if row['time'] == 25)
    i = int(np.argmin(abs(track.times - 1)))
    assert track.valid[i]
    x, y = track.lm[i, [23, 24], :2].mean(0)
    left, top, right, bottom = label['box']
    assert left <= x <= right and top <= y <= bottom
