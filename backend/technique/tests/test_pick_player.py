"""Tap a player, then track them: each player of a two-player clip in turn (real samples)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from technique import media, people, pose

SAMPLES = Path(__file__).resolve().parents[3] / "samples"


@pytest.mark.parametrize("name", ["IMG_8782.MOV", "coaching-demo.mp4"])
def test_each_tapped_player_is_the_one_tracked(name, tmp_path):
    video = SAMPLES / name
    if not video.exists():
        pytest.skip(f"put {name} in samples/")
    found = people.detect(people.sample_frames(str(video), 6))
    frame = found["frame"]
    assert len(frame["boxes"]) >= 2, "the picker frame should show both players"
    t = frame["time"]
    clip = media.make_proxy(video, tmp_path / "clip.mp4", height=720, fps=30, start=t, end=t + 6)
    for pick in frame["boxes"][:2]:
        box = pick["box"]
        track = pose.extract_pose(clip, stride=3, identity=pose.identity_from_box(video, t, tuple(box)))
        # Right after the tap the tracked hips must be inside the tapped box, never the other player's.
        first = np.flatnonzero(track.valid)[0]
        hx, hy = track.lm[first, [23, 24], :2].mean(0)
        # The table can hide a far player's hips, so the tapped box may stop just above them.
        pad = .1 * (box[3] - box[1])
        assert box[0] <= hx <= box[2] and box[1] - pad <= hy <= box[3] + pad, (name, pick["id"], hx, hy, box)
        # Over the whole clip the track keeps the tapped player's size in the frame: near and
        # far players can share an x position (IMG_8782), but not their height. (Hip height
        # doesn't work as a check: the table hides a far player's hips and his box ends above them.)
        other = next(b["box"] for b in frame["boxes"] if b["id"] != pick["id"])
        height = np.median(np.ptp(track.lm[track.valid, :, 1], axis=1))
        mine, theirs = box[3] - box[1], other[3] - other[1]
        assert abs(height - mine) < abs(height - theirs), (name, pick["id"], height, mine, theirs)
