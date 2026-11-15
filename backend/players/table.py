"""Estimate a player's height from the table in the frame (76 cm high, 274 cm long).

Two cues, used when they are available and agree:
  * height: the table top edge above the player's feet is 76 cm at the player's depth;
  * length: in a side-on view, the long edge of the table top is 274 cm.
Returns None when no table is found; the result is approximate (+/- ~10 cm)."""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from technique.pose import L_ANKLE, NOSE, R_ANKLE, PoseTrack, _interp_nan

TABLE_HEIGHT_CM = 76.0
TABLE_LENGTH_CM = 274.0
CROWN = 1.06  # nose-to-ankle covers ~94% of stature (crown above the nose, sole below the ankle)


def table_mask(frame: np.ndarray) -> np.ndarray:
    """Blue or green table-top pixels."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(hsv, (95, 90, 50), (130, 255, 255))
    green = cv2.inRange(hsv, (40, 90, 40), (85, 255, 230))
    m = cv2.bitwise_or(blue, green)
    return cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))


def find_table(frame: np.ndarray) -> Optional[dict]:
    m = table_mask(frame)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = m.shape
    cnts = [c for c in cnts if cv2.contourArea(c) > 0.015 * h * w]
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    x, y, cw, ch = cv2.boundingRect(c)
    if cw < 1.2 * ch:  # a table top seen from any normal camera angle is wider than tall
        return None
    pts = c.reshape(-1, 2)
    return {"bbox": (int(x), int(y), int(cw), int(ch)), "top_y_at": lambda px: _top_y(pts, px),
            "long_edge_px": float(cw), "side_on": cw > 3.0 * ch}


def _top_y(pts: np.ndarray, px: float) -> float:
    near = pts[np.abs(pts[:, 0] - px) < max(8, 0.05 * np.ptp(pts[:, 0]))]
    return float(near[:, 1].min()) if len(near) else float(pts[:, 1].min())


def estimate_height_cm(video: str, track: PoseTrack, samples: int = 8) -> Optional[dict]:
    if not len(track.times) or not track.valid.any():
        return None
    xy = _interp_nan(track.lm[:, :, :2]) * np.array([track.width, track.height])
    idx = np.linspace(0, len(track.times) - 1, samples).astype(int)
    idx = [i for i in idx if track.valid[i]]
    cap = cv2.VideoCapture(video)
    by_height, by_length = [], []
    stride = int(track.meta.get("stride", 1))
    for i in idx:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i * stride)
        ok, frame = cap.read()
        if not ok:
            continue
        t = find_table(frame)
        if not t:
            continue
        feet_y = max(xy[i, L_ANKLE, 1], xy[i, R_ANKLE, 1])
        person_px = (feet_y - xy[i, NOSE, 1]) * CROWN
        feet_x = (xy[i, L_ANKLE, 0] + xy[i, R_ANKLE, 0]) / 2
        bx, _, bw, _ = t["bbox"]
        edge_x = float(np.clip(feet_x, bx, bx + bw))
        rise = feet_y - t["top_y_at"](edge_x)
        if rise > 0.15 * person_px:
            by_height.append(person_px * TABLE_HEIGHT_CM / rise)
        if t["side_on"]:
            by_length.append(person_px * TABLE_LENGTH_CM / t["long_edge_px"])
    cap.release()
    ests = {k: float(np.median(v)) for k, v in (("table_height", by_height), ("table_length", by_length)) if v}
    ests = {k: v for k, v in ests.items() if 135 <= v <= 215}
    if not ests:
        return None
    if len(ests) == 2 and abs(ests["table_height"] - ests["table_length"]) / ests["table_height"] > 0.15:
        ests.pop("table_length")  # disagree: the height cue is measured at the player's depth
    cm = float(np.mean(list(ests.values())))
    return {"height_cm": round(cm), "method": "+".join(sorted(ests)), "approximate": True}
