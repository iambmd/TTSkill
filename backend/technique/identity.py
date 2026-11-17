"""Keep the initially selected player using torso appearance across occlusions and cuts."""
from __future__ import annotations

import cv2
import numpy as np


def appearance(frame: np.ndarray, lm: np.ndarray) -> np.ndarray:
    """HSV torso histogram, excluding the background outside the shoulder/hip polygon."""
    h, w = frame.shape[:2]
    polygon = (lm[[11, 12, 24, 23], :2] * [w, h]).astype(np.int32)
    mask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(mask, polygon, 255)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], mask, [12, 4], [0, 180, 0, 256])
    # Nearby colour bins should still match under a lighting/camera change.
    hist = .5 * hist + .25 * (np.roll(hist, 1, axis=0) + np.roll(hist, -1, axis=0))
    hist = cv2.GaussianBlur(hist, (3, 1), .65).ravel()
    return hist / max(float(hist.sum()), 1)


# Colour distance to the frozen template. The selected player scores ~.2-.75 on the eval
# clips as lighting and pose change; a different shirt ~.9-1.0.
STRICT = .55     # accepted outright
LOOSE = .8       # accepted only when clearly the best match in frame, or continuing in place
MARGIN = .15     # a loose match must beat every other person by this much
NEAR = .1        # normalized hip movement that still counts as the same place


class PlayerIdentity:
    """One persistent selected ID; abstain when re-identification is ambiguous.

    The initial torso template is frozen to prevent drift onto a different player.
    Position breaks ties during continuous play, but appearance survives side switches.
    """

    def __init__(self, reference: np.ndarray | None = None) -> None:
        self.reference = reference
        self.centre: np.ndarray | None = None
        self.missing = 0

    def select(self, poses: list[np.ndarray], looks: list[np.ndarray],
               cut: bool = False) -> int | None:
        if cut:
            self.centre = None
        if not poses:
            self.missing += 1
            return None
        centres = [p[[23, 24], :2].mean(0) for p in poses]
        if self.reference is None:
            best = max(range(len(poses)), key=lambda i: np.linalg.norm(
                poses[i][[11, 12], :2].mean(0) - centres[i]))
            if looks[best].sum() == 0:
                return None
            self.reference = looks[best].copy()
        else:
            distances = [float(np.linalg.norm(np.sqrt(h) - np.sqrt(self.reference)) / np.sqrt(2))
                         for h in looks]
            eligible = [i for i, d in enumerate(distances) if d < LOOSE]
            if not eligible:
                self.missing += 1
                return None
            tracking = self.centre is not None and self.missing < 5
            def cost(i: int) -> float:
                continuity = min(float(np.linalg.norm(centres[i] - self.centre)), .5) if tracking else 0.
                return distances[i] + .25 * continuity
            ranked = sorted(eligible, key=cost)
            best = ranked[0]
            if len(ranked) > 1 and cost(ranked[1]) - cost(best) < .05:
                self.missing += 1
                return None
            if distances[best] >= STRICT:
                # A lone loose match after a cut could be anyone; never guess there.
                clear = min((d for i, d in enumerate(distances) if i != best), default=0.) - distances[best] >= MARGIN
                in_place = tracking and float(np.linalg.norm(centres[best] - self.centre)) < NEAR
                if not (clear or in_place):
                    self.missing += 1
                    return None
        self.centre = centres[best]
        self.missing = 0
        return best
