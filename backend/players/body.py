"""Body profile from a pose track: limb ratios, stance width and the joint-angle curves
of one stroke. Pros (players/build.py) and users (app/pipelines.run_match) go through the
same code, so their numbers are comparable."""
from __future__ import annotations

import numpy as np

from technique.pose import (L_ANKLE, L_ELBOW, L_HIP, L_KNEE, L_SHOULDER, L_WRIST, NOSE, R_ANKLE,
                            R_ELBOW, R_HIP, R_KNEE, R_SHOULDER, R_WRIST, PoseTrack, _angle,
                            _interp_nan)

CURVE_POINTS = 40
JOINTS = ("elbow", "shoulder", "knee", "trunk_turn")
JOINT_NAMES = {"elbow": "bat-arm elbow", "shoulder": "bat-arm shoulder lift",
               "knee": "knee bend", "trunk_turn": "shoulder turn vs hips"}


def _points(track: PoseTrack) -> tuple[np.ndarray, bool]:
    """(N,33,3) world landmarks in metres when present (rotation-free), else image pixels."""
    w = track.world
    if w.size and np.isfinite(w).any() and np.nanmax(np.abs(w)) > 1e-6:
        return _interp_nan(w), True
    xy = _interp_nan(track.lm[:, :, :2]) * np.array([track.width, track.height])
    return np.concatenate([xy, np.zeros((*xy.shape[:2], 1))], axis=-1), False


def _seg(p: np.ndarray, a: int, b: int) -> np.ndarray:
    return np.linalg.norm(p[:, a] - p[:, b], axis=-1)


def body_ratios(track: PoseTrack) -> dict:
    """Scale-free proportions (medians over visible frames). height_units is the stature
    in the track's own units, used with the table to estimate height in cm."""
    p, metric = _points(track)
    ok = track.valid if len(track.valid) == len(p) else np.ones(len(p), bool)
    if ok.sum() < 3:
        ok = np.ones(len(p), bool)
    p = p[ok]
    med = lambda v: float(np.nanmedian(v))
    upper_arm = med((_seg(p, L_SHOULDER, L_ELBOW) + _seg(p, R_SHOULDER, R_ELBOW)) / 2)
    forearm = med((_seg(p, L_ELBOW, L_WRIST) + _seg(p, R_ELBOW, R_WRIST)) / 2)
    shoulder_w = med(_seg(p, L_SHOULDER, R_SHOULDER))
    sh_mid = (p[:, L_SHOULDER] + p[:, R_SHOULDER]) / 2
    hip_mid = (p[:, L_HIP] + p[:, R_HIP]) / 2
    torso = med(np.linalg.norm(sh_mid - hip_mid, axis=-1))
    # Longest leg in each frame: the bent leg foreshortens, the straighter one is closer to true.
    legs = np.maximum(_seg(p, L_HIP, L_KNEE) + _seg(p, L_KNEE, L_ANKLE),
                      _seg(p, R_HIP, R_KNEE) + _seg(p, R_KNEE, R_ANKLE))
    leg = float(np.nanpercentile(legs, 75))
    head_neck = med(np.linalg.norm(p[:, NOSE] - sh_mid, axis=-1)) * 1.6  # nose-to-crown allowance
    height = leg + torso + head_neck
    stance = med(_seg(p, L_ANKLE, R_ANKLE))
    span = shoulder_w + 2 * (upper_arm + forearm)
    return {
        "arm_span_to_height": round(span / height, 3),
        "leg_to_torso": round(leg / torso, 3),
        "shoulder_width_to_height": round(shoulder_w / height, 3),
        "stance_width_to_shoulders": round(stance / shoulder_w, 3),
        "height_units": round(height, 4),
        "units": "m" if metric else "px",
    }


def angle_curves(track: PoseTrack, side: str, contact_i: int,
                 before_s: float = 0.6, after_s: float = 0.45) -> dict:
    """Joint angles (degrees) from `before_s` before contact to `after_s` after it,
    resampled to CURVE_POINTS samples. Contact sits at the same index for everyone."""
    p, _ = _points(track)
    n = len(p)
    fps = track.fps or 30.0
    a = max(0, contact_i - int(before_s * fps))
    b = min(n, contact_i + int(after_s * fps) + 1)
    if b - a < 4:
        a, b = 0, n
    sh, el, wr, hp = ((R_SHOULDER, R_ELBOW, R_WRIST, R_HIP) if side != "left"
                      else (L_SHOULDER, L_ELBOW, L_WRIST, L_HIP))
    seg = p[a:b]
    elbow = _angle(seg[:, sh], seg[:, el], seg[:, wr])
    shoulder = _angle(seg[:, hp], seg[:, sh], seg[:, el])
    knee = (_angle(seg[:, L_HIP], seg[:, L_KNEE], seg[:, L_ANKLE])
            + _angle(seg[:, R_HIP], seg[:, R_KNEE], seg[:, R_ANKLE])) / 2
    # Shoulder line vs hip line seen from above (x-z plane); 2D tracks fall back to image x-y.
    s_vec = (seg[:, R_SHOULDER] - seg[:, L_SHOULDER])[:, [0, 2]]
    h_vec = (seg[:, R_HIP] - seg[:, L_HIP])[:, [0, 2]]
    if not np.abs(s_vec[:, 1]).any():
        s_vec = (seg[:, R_SHOULDER] - seg[:, L_SHOULDER])[:, :2]
        h_vec = (seg[:, R_HIP] - seg[:, L_HIP])[:, :2]
    cross = s_vec[:, 0] * h_vec[:, 1] - s_vec[:, 1] * h_vec[:, 0]
    dot = (s_vec * h_vec).sum(-1)
    turn = np.degrees(np.abs(np.arctan2(cross, dot)))
    src = np.linspace(0, 1, len(seg))
    dst = np.linspace(0, 1, CURVE_POINTS)
    curves = {k: np.interp(dst, src, np.nan_to_num(v)).round(1).tolist()
              for k, v in (("elbow", elbow), ("shoulder", shoulder), ("knee", knee), ("trunk_turn", turn))}
    curves["contact_index"] = int(round((contact_i - a) / max(1, b - a - 1) * (CURVE_POINTS - 1)))
    return curves
