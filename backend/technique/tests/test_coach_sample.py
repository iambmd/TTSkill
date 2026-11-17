"""Real-video regression for the provisional teal-shirt backhand; no generated data in Git."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from technique import media, pose, strokes

ROOT = Path(__file__).resolve().parents[3]
LABEL = json.loads((ROOT / 'backend/eval/regressions/coach_backhand.json').read_text())
SAMPLE = ROOT / LABEL['video']


@pytest.fixture(scope='module')
def backhand_track(tmp_path_factory):
    if not SAMPLE.exists():
        pytest.skip('put coach_demo.mp4 in samples/')
    out = tmp_path_factory.mktemp('coach-backhand')
    start, end = LABEL['window']
    clip = media.make_proxy(SAMPLE, out / 'clip.mp4', height=720, fps=30, start=start, end=end)
    track = pose.extract_pose(clip, identity=pose.initial_identity(SAMPLE))
    pose.require_player(track)
    return track, round((LABEL['contact_s'] - start) * track.fps)


def test_requested_backhand_is_preserved_on_coach_sample(backhand_track):
    tr, contact = backhand_track
    key, _ = strokes.detect(tr, LABEL['hand'], contact, wing=LABEL['wing'])
    assert strokes.STROKE_TYPES[key].stroke == 'backhand'
    # The selected body belongs to the near/left player, not the far/right opponent.
    assert tr.lm[tr.valid, 23, 0].mean() < .5


@pytest.mark.xfail(strict=True, reason='Occluded wrist/world-depth noise still misclassifies this backhand; see eval README')
def test_automatic_backhand_on_coach_sample(backhand_track):
    tr, contact = backhand_track
    key, _ = strokes.detect(tr, LABEL['hand'], contact)
    assert strokes.STROKE_TYPES[key].stroke == LABEL['wing']
