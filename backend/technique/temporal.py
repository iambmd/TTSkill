"""Optional DTW wing classifier over contact-centred, body-relative pose sequences."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from .pose import PoseTrack, _angle
from .strokes import _points


def sequence(track: PoseTrack, side: str, contact_i: int, frames: int = 21) -> np.ndarray | None:
    """Canonical bat-side coordinates, mirrored for left-handers; reject poorly seen swings."""
    if len(track.times) < 5:
        return None
    c = int(np.clip(contact_i, 0, len(track.times) - 1))
    indices = np.flatnonzero(abs(track.times - track.times[c]) <= .35)
    if len(indices) < 5 or track.valid[indices].mean() < .7:
        return None
    p = _points(track)[indices]
    sh, other, el, wrist = (12, 11, 14, 16) if side == 'right' else (11, 12, 13, 15)
    centre = (p[:, 11] + p[:, 12]) / 2
    hips = (p[:, 23] + p[:, 24]) / 2
    torso = np.linalg.norm(centre - hips, axis=1) + 1e-6
    axis = p[:, sh] - p[:, other]
    axis /= np.linalg.norm(axis, axis=1)[:, None] + 1e-6
    rel_w, rel_e = p[:, wrist] - centre, p[:, el] - centre
    values = np.column_stack(((rel_w * axis).sum(-1) / torso,
                              (rel_e * axis).sum(-1) / torso,
                              rel_w[:, 1] / torso,
                              _angle(p[:, sh], p[:, el], p[:, wrist]) / 180))
    if not np.isfinite(values).all():
        return None
    t = track.times[indices]
    return np.column_stack([np.interp(np.linspace(t[0], t[-1], frames), t, v) for v in values.T])


def distance(a: np.ndarray, b: np.ndarray) -> float:
    """Average DTW cost with a narrow warping band to retain stroke order."""
    prev = np.full(len(b) + 1, np.inf)
    prev[0] = 0
    for i, row in enumerate(a):
        cur = np.full(len(b) + 1, np.inf)
        for j in range(max(0, i - 4), min(len(b), i + 5)):
            cur[j + 1] = float(np.linalg.norm(row - b[j])) + min(prev[j], prev[j + 1], cur[j])
        prev = cur
    return float(prev[-1] / max(len(a), len(b)))


def predict(query: np.ndarray, templates: list[dict]) -> tuple[str | None, dict]:
    scores = {}
    for wing in ('forehand', 'backhand'):
        ds = sorted(distance(query, np.asarray(t['sequence'])) for t in templates if t['wing'] == wing)
        if len(ds) < 3:
            return None, {'reason': 'need three templates per wing'}
        scores[wing] = float(np.mean(ds[:3]))
    best = min(scores, key=scores.get)
    other = max(scores, key=scores.get)
    margin = (scores[other] - scores[best]) / max(scores[other], 1e-6)
    # No confident label for out-of-domain or nearly tied templates.
    return (best if margin >= .2 and scores[best] < 1.0 else None), {'distances': scores, 'margin': margin}


def classify(track: PoseTrack, side: str, contact_i: int) -> tuple[str | None, dict]:
    path = os.environ.get('TTSKILL_STROKE_MODEL')
    if not path:
        return None, {}
    query = sequence(track, side, contact_i)
    if query is None:
        return None, {'reason': 'insufficient visible sequence'}
    data = json.loads(Path(path).read_text())
    if data.get('version') != 1:
        raise ValueError('Unsupported stroke template version')
    return predict(query, data['templates'])
