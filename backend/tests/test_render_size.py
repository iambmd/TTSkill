"""The breakdown renders at 720x1280 for Coach (same layout as 1080x1920)."""
from __future__ import annotations

import json
import subprocess

import numpy as np

from technique.pose import PoseTrack


def standing(n: int, height: float = .7) -> PoseTrack:
    """A standing player in the middle of the frame for n frames."""
    lm = np.zeros((n, 33, 4), np.float32)
    lm[:, :, 0], lm[:, :, 3] = .5, 1.0
    lm[:, :, 1] = np.linspace(.15, .15 + height, 33)
    return PoseTrack(fps=30.0, width=640, height=360, times=np.arange(n) / 30, lm=lm,
                     world=np.zeros((n, 33, 3), np.float32), meta={"stride": 1})


def test_the_breakdown_renders_at_720p(media, tmp_path):
    from technique.render import render_breakdown
    from technique.schema import Step, StrokeBreakdown
    n = 90
    track = standing(n)
    b = StrokeBreakdown(stroke="forehand", headline="Sit low", grip="g", stance="s", swing_path="p",
                        contact_point="c", follow_through="f", recap="r", drill="d",
                        steps=[Step(title=t, lines=["a", "b"], key_time_s=k) for t, k in (("LOAD LOW", .5), ("HIT", 1.0), ("END", 1.5))])
    out = render_breakdown(str(media["ok"]), track, b, str(tmp_path / "b.mp4"), "right", height=1280, preset="superfast")
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                       "stream=width,height", "-of", "json", out], capture_output=True, check=True).stdout)
    assert (probe["streams"][0]["width"], probe["streams"][0]["height"]) == (720, 1280)
