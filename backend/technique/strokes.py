"""Stroke types: labels, how each one moves (which way the bat goes through contact), and
auto-detection from the pose track or from the user's text.

The broad `stroke` (forehand/backhand/serve/...) is kept for older callers; a stroke type
refines it and picks the coaching template, the key-moment search and the Claude prompt."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    from .pose import PoseTrack


@dataclass(frozen=True)
class StrokeType:
    key: str
    label: str
    stroke: str          # broad stroke: forehand | backhand | serve
    direction: str       # bat travel through contact: up | down | any
    window_s: float      # how far before/after contact preparation and finish are searched
    phases: tuple[str, str, str]
    focus: str           # what a coach looks at; goes into the Claude prompt


STROKE_TYPES: dict[str, StrokeType] = {s.key: s for s in [
    StrokeType("forehand_topspin", "Forehand topspin", "forehand", "up", 0.6,
               ("load", "contact", "follow-through"),
               "low-to-high brush driven by the legs and waist; contact in front at the top of the bounce"),
    StrokeType("forehand_drive", "Forehand drive", "forehand", "up", 0.5,
               ("short backswing", "hit through", "compact recovery"),
               "flatter forward swing with a slightly closed bat, hitting through the ball at the peak"),
    StrokeType("forehand_loop_backspin", "Forehand loop vs backspin", "forehand", "up", 0.8,
               ("drop low", "lift through contact", "high finish"),
               "start low with deep knees, swing steeply upward to lift the backspin, contact as the ball drops"),
    StrokeType("backhand_topspin", "Backhand topspin", "backhand", "up", 0.5,
               ("set the elbow", "contact", "recover"),
               "elbow forward as a pivot, forearm opens forward and up, contact in front of the body"),
    StrokeType("backhand_flick", "Backhand flick", "backhand", "up", 0.4,
               ("step in", "wrist flick at the peak", "get out of the table"),
               "step under the table, cock the wrist, short sharp flick forward and up over the ball"),
    StrokeType("backhand_push", "Backhand push", "backhand", "down", 0.45,
               ("open the bat", "push under the ball", "reset"),
               "open bat face, short forward-and-down stroke under the ball, contact early after the bounce"),
    StrokeType("chop", "Chop", "chop", "down", 0.7,
               ("bat up high", "cut down at contact", "finish low"),
               "away from the table, high-to-low cut under the ball as it drops, open bat face"),
    StrokeType("serve", "Serve", "serve", "any", 0.5,
               ("toss", "brush contact", "ready for ball three"),
               "legal open-palm toss, fast wrist brush low over the table, disguise the spin"),
]}

# Old broad strokes that map straight to a type; forehand/backhand still auto-detect the type
# within that wing; block and footwork have no type.
LEGACY_TYPE = {"serve": "serve", "flick": "backhand_flick"}


def resolve(stroke_type: Optional[str]) -> Optional[str]:
    """Normalise a user value to a type key. Blank or 'auto' -> None (auto-detect)."""
    key = (stroke_type or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in ("", "auto"):
        return None
    if key not in STROKE_TYPES:
        raise ValueError(f"unknown stroke type: {stroke_type}")
    return key


def label(key_or_stroke: str) -> str:
    st = STROKE_TYPES.get(key_or_stroke or "")
    return st.label if st else (key_or_stroke or "stroke").capitalize()


def _points(track: PoseTrack) -> np.ndarray:
    """World landmarks (metres, rotation-free) when MediaPipe gave them, else pixels."""
    from .pose import _interp_nan  # pose pulls in OpenCV; keep this module light for the API

    w = track.world
    if w.size and np.isfinite(w).any() and np.nanmax(np.abs(w)) > 1e-6:
        return _interp_nan(w)
    return _interp_nan(track.lm[:, :, :2]) * np.array([track.width, track.height])


def features(track: PoseTrack, side: str, contact_i: int) -> dict:
    """Body-relative bat-hand motion around contact, in torso lengths.
    side_score > 0: wrist on the bat-arm side of the body (forehand); < 0: across (backhand).
    rise > 0: the wrist moved up through contact. low_start: wrist below the hips before it."""
    from .pose import L_HIP, L_SHOULDER, L_WRIST, R_HIP, R_SHOULDER, R_WRIST

    p = _points(track)
    n = len(p)
    c = int(np.clip(contact_i, 0, n - 1))
    bat_sh, free_sh = (R_SHOULDER, L_SHOULDER) if side != "left" else (L_SHOULDER, R_SHOULDER)
    wi = R_WRIST if side != "left" else L_WRIST
    sh_mid = (p[:, L_SHOULDER] + p[:, R_SHOULDER]) / 2
    hip_mid = (p[:, L_HIP] + p[:, R_HIP]) / 2
    torso = float(np.median(np.linalg.norm(sh_mid - hip_mid, axis=1))) + 1e-6
    rng = slice(max(0, c - 2), min(n, c + 3))
    axis = p[rng, bat_sh] - p[rng, free_sh]
    rel = p[rng, wi] - sh_mid[rng]
    side_score = float(np.mean((rel * axis).sum(-1) / ((axis ** 2).sum(-1) + 1e-9)))
    wy = (p[:, wi, 1] - hip_mid[:, 1]) / torso          # image and world y both point down
    fps = track.fps or 30.0
    a, b = max(0, c - int(0.35 * fps)), min(n - 1, c + int(0.3 * fps))
    rise = float(wy[a] - wy[b])
    low_start = float(np.max(wy[max(0, c - int(0.6 * fps)):c + 1]))
    path = float(np.linalg.norm(np.diff(p[a:b + 1, wi], axis=0), axis=-1).sum() / torso)
    return {"side_score": round(side_score, 2), "rise": round(rise, 2),
            "low_start": round(low_start, 2), "path": round(path, 2)}


def classify(f: dict, wing: Optional[str] = None) -> str:
    """Pick a stroke type from `features()`. `wing` forces forehand/backhand when known."""
    wing = wing or ("forehand" if f["side_score"] > 0.15 else "backhand")
    rise, path = f["rise"], f["path"]
    if wing == "backhand":
        if rise < -0.1:
            return "backhand_push" if path < 1.5 else "chop"
        if rise < 0.3 and path < 1.2:
            return "backhand_flick"
        return "backhand_topspin"
    if rise < -0.3:
        return "chop"
    if rise > 0.8 and f["low_start"] > 0.2:
        return "forehand_loop_backspin"
    if rise > 0.35:
        return "forehand_topspin"
    return "forehand_drive"


def detect(track: PoseTrack, side: str, contact_i: int, wing: Optional[str] = None) -> tuple[str, dict]:
    f = features(track, side, contact_i)
    return classify(f, wing), f


def from_text(text: str) -> Optional[str]:
    """Best guess from a written description; None when nothing matches."""
    t = (text or "").lower()
    if "chop" in t:
        return "chop"
    if "serve" in t or "serving" in t:
        return "serve"
    if "flick" in t or "banana" in t or "chiquita" in t:
        return "backhand_flick"
    if "push" in t:
        return "backhand_push"
    if "backhand" in t:
        return "backhand_topspin"
    if "backspin" in t or "underspin" in t:
        return "forehand_loop_backspin"
    if "drive" in t or "smash" in t or "flat" in t:
        return "forehand_drive"
    if "forehand" in t or "loop" in t or "topspin" in t:
        return "forehand_topspin"
    return None
