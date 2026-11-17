"""Experimental wing evidence from the backswing in a pose-calibrated body frame."""
from __future__ import annotations

import numpy as np

from technique.pose import PoseTrack

MARGIN = .25  # torso lengths: ambiguous motions retain the existing classifier


def evidence(track: PoseTrack, side: str, contact_i: int) -> dict:
    """Use observed world points only; abstain when the wrist or body basis is unclear."""
    n = len(track.times)
    if n < 5 or side not in ('left', 'right'):
        return {'wing': None, 'reason': 'insufficient track'}
    wi = 16 if side == 'right' else 15
    p = track.world
    body = [11, 12, 23, 24]
    good = track.valid & np.isfinite(p[:, body]).all(axis=(1, 2)) & (track.lm[:, body, 3].min(axis=1) >= .5)
    hips = p[:, [23, 24]].mean(axis=1)
    shoulders = p[:, [11, 12]].mean(axis=1)
    lengths = np.linalg.norm(shoulders - hips, axis=1)
    good &= lengths > 1e-3
    if good.sum() < 5:
        return {'wing': None, 'reason': 'no reliable world basis'}
    torso = float(np.median(lengths[good]))
    axes = p[:, 12] - p[:, 11]
    axes[:, 1] = 0
    sizes = np.linalg.norm(axes, axis=1)
    good &= sizes > .2 * torso
    if good.sum() < 5:
        return {'wing': None, 'reason': 'shoulder axis unclear'}
    axis = np.median(axes[good] / sizes[good, None], axis=0)
    stability = float(np.linalg.norm(axis))
    if stability < .5:
        return {'wing': None, 'reason': 'body orientation changes'}
    axis /= stability
    forward = np.array([-axis[2], 0., axis[0]])
    c = int(np.clip(contact_i, 0, n - 1))
    t = track.times[c]
    window = (track.times >= t - .35) & (track.times <= t - .08)
    reliable = window & good & (track.lm[:, wi, 3] >= .5) & np.isfinite(p[:, wi]).all(axis=1)
    if reliable.sum() < 3 or reliable.sum() < .6 * window.sum():
        return {'wing': None, 'reason': 'backswing wrist occluded'}
    wrist = (p[reliable, wi] - hips[reliable]) / torso
    lateral = float(np.median(wrist @ axis)) * (1 if side == 'right' else -1)
    front = float(np.median(wrist @ forward))
    score = lateral - front
    wing = ('forehand' if score > MARGIN else 'backhand' if score < -MARGIN else None)
    return {'wing': wing, 'lateral': round(lateral, 3), 'forward': round(front, 3),
            'margin': round(abs(score), 3), 'samples': int(reliable.sum()),
            'reason': 'backswing geometry' if wing else 'ambiguous backswing'}
