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
    found = people.detect(people.sample_frames(str(video)))
    frame = found["frame"]
    # The players' boxes (background people's boxes follow them, for "Show everyone we saw").
    boxes = [b for b in frame["boxes"] if b["id"] < len(found["candidates"])]
    assert len(boxes) >= 2, "the picker frame should show both players"
    t = frame["time"]
    clip = media.make_proxy(video, tmp_path / "clip.mp4", height=720, fps=30, start=t, end=t + 6)
    for pick in boxes[:2]:
        box = pick["box"]
        track = pose.extract_pose(clip, stride=3, identity=pose.identity_from_box(video, t, tuple(box)))
        # Right after the tap the tracked hips must be inside the tapped box, never the other player's.
        first = np.flatnonzero(track.valid)[0]
        hx, hy = track.lm[first, [23, 24], :2].mean(0)
        # The table can hide a far player's hips, so the tapped box may stop just above them.
        pad = .1 * (box[3] - box[1])
        assert box[0] <= hx <= box[2] and box[1] - pad <= hy <= box[3] + pad, (name, pick["id"], hx, hy, box)
        # Right after the tap the track keeps the tapped player's size in the frame: near and
        # far players can share an x position (IMG_8782), but not their height. (Hip height
        # doesn't work as a check: the table hides a far player's hips and his box ends above them.)
        # Only the first 2 s: on the montage the 36.2 s frame is 3.5 s before a cut to a clip
        # where the user plays from the far side, and the track rightly follows him there.
        other = next(b["box"] for b in boxes if b["id"] != pick["id"])
        soon = np.flatnonzero(track.valid & (track.times < 2.0))
        # Measured like the picker's boxes (box_of pads the head and feet), not the bare landmarks.
        height = np.median([people.box_of(track.lm[i])[3] - people.box_of(track.lm[i])[1] for i in soon])
        mine, theirs = box[3] - box[1], other[3] - other[1]
        assert abs(height - mine) < abs(height - theirs), (name, pick["id"], height, mine, theirs)
