"""MediaPipe pose extraction + simple swing analysis (pure numpy/scipy on landmarks)."""
from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks

from limits import LIMITS
from .errors import NoPlayer

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
)

# MediaPipe landmark indices (player's own left/right)
NOSE = 0
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28

CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (24, 26), (26, 28), (27, 31), (28, 32), (27, 29), (28, 30),
    (15, 19), (16, 20), (0, 11), (0, 12),
]


def model_path() -> Path:
    env = os.environ.get("POSE_MODEL_PATH")
    if env:
        return Path(env)
    p = Path.home() / ".cache" / "ttskill" / "pose_landmarker_full.task"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, p)
    return p


@dataclass
class PoseTrack:
    fps: float
    width: int
    height: int
    times: np.ndarray            # (N,) seconds, relative to the analysed video
    lm: np.ndarray               # (N,33,4) normalized x,y,z,visibility; NaN when no person
    world: np.ndarray            # (N,33,3) metres, hip-centred; NaN when no person
    meta: dict = field(default_factory=dict)

    @property
    def valid(self) -> np.ndarray:
        return ~np.isnan(self.lm[:, 0, 0])

    def px(self, i: int) -> np.ndarray:
        """(33,2) pixel coords for frame i."""
        return self.lm[i, :, :2] * np.array([self.width, self.height])


# Below this share of frames with a player, the cues and overlay would track noise.
MIN_VISIBLE = LIMITS["pose"]["min_visible_ratio"]
_CLEARER = "Film a clearer clip: the whole body in frame, side-on if you can, in good light."


_LOST_PICK = ("Pick them in a frame where they're clearly in view, film closer, or trim the video "
              "to the part where they play.")


def require_player(track: PoseTrack, min_ratio: float = MIN_VISIBLE, picked: bool = False) -> float:
    """The share of frames with a player; NoPlayer if it is under `min_ratio`, so a job asks
    for a clearer clip instead of rendering a bad video. picked: the user tapped this player,
    so say they were lost (the tracker never swaps in someone else)."""
    ratio = float(track.valid.mean()) if len(track.valid) else 0.0
    if picked and ratio < min_ratio:
        seen = f"only in {int(ratio * 100)}% of the clip" if ratio else "anywhere in the analysed part of the clip"
        raise NoPlayer(f"We lost the player you picked: we could see them {seen}. {_LOST_PICK}")
    if ratio == 0:
        raise NoPlayer(f"We couldn't find a player in this clip. {_CLEARER}")
    if ratio < min_ratio:
        # Rounded down, so 39.6% doesn't read as "40%" next to a 40% minimum.
        raise NoPlayer(f"We could only see the player in {int(ratio * 100)}% of the clip. {_CLEARER}")
    return ratio


# Four overlapping quarters of the frame. A far-side player is too small for the detector in
# the full or half frame (IMG_8782's opponent: found in 1 of 6 frames); in a quarter he is
# twice the size. Used to find players for the picker, not on every tracked frame (4x cost).
QUARTERS = [(0., 0., .55, .6), (.45, 0., 1., .6), (0., .4, .55, 1.), (.45, .4, 1., 1.)]


MIN_CROP = 256   # px: a smaller crop is upscaled before pose, so a far player gets enough pixels


def _pose_candidates(frame: np.ndarray, landmarker, mp,
                     extra: list[tuple[float, float, float, float]] | None = None,
                     first: list[tuple[float, float, float, float]] | None = None
                     ) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Detect visible upright people consistently during seed selection and tracking.
    extra: more (left, top, right, bottom) crops to search, e.g. QUARTERS for small players.
    first: crops searched before the usual ones, so their (zoomed) landmarks win duplicates."""
    h, w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    # Wide gym views can hallucinate a body on the table. Half-frame
    # crops give each player enough pixels; the full view covers centre crossings.
    regions = [(0., 0., 1., 1.)] if w / h < 1.5 else [(0., 0., .6, 1.), (.4, 0., 1., 1.), (0., 0., 1., 1.)]
    people, world_people = [], []
    for left, top, right, bottom in (first or []) + regions + (extra or []):
        crop = np.ascontiguousarray(rgb[int(top * h):int(bottom * h), int(left * w):int(right * w)])
        if 0 < min(crop.shape[:2]) < MIN_CROP:
            scale = MIN_CROP / min(crop.shape[:2])
            crop = cv2.resize(crop, (round(crop.shape[1] * scale), round(crop.shape[0] * scale)),
                              interpolation=cv2.INTER_CUBIC)
        if crop.size == 0:
            continue
        result = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=crop))
        for k, pl in enumerate(result.pose_landmarks):
            p = np.array([[v.x * (right-left) + left, v.y * (bottom-top) + top, v.z * (right-left),
                           v.visibility or 0.] for v in pl], np.float32)
            if implausible(p[None], w, h)[0] or np.min(p[[11, 12, 23, 24], 3]) < .5:
                continue
            centre = p[[23, 24], :2].mean(0)
            if any(np.linalg.norm(centre - q[[23, 24], :2].mean(0)) < .06 for q in people):
                continue
            people.append(p)
            world_people.append(np.array([[v.x, v.y, v.z] for v in result.pose_world_landmarks[k]],
                                         np.float32))
    return people, world_people


def _landmarker_options(num_poses: int = 3):
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python import vision

    return vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path())),
        running_mode=vision.RunningMode.IMAGE,
        num_poses=num_poses,
        min_pose_detection_confidence=0.4,
        min_tracking_confidence=0.4,
    )


class Follower:
    """The per-frame part of tracking one player: find the people, keep the one whose looks
    match (PlayerIdentity), search zoomed crops when they are small or lost. extract_pose
    feeds it every stride-th frame; hitpose feeds it full-rate frames around ball contacts
    and a few frames a second in between."""

    def __init__(self, landmarker, mp, w: int, h: int, identity: np.ndarray | None = None) -> None:
        from .identity import PlayerIdentity

        self.lmk, self.mp, self.w, self.h = landmarker, mp, w, h
        self.tracker = PlayerIdentity(identity)
        self.previous_scene = None
        self.n = 0

    def step(self, frame: np.ndarray, cut: bool | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Landmarks (33x4) and world landmarks (33x3) of the followed player, NaN if not seen.
        cut: a known jump in time (hitpose's gaps); otherwise a scene change decides."""
        from .identity import signature
        from .people import box_of

        people, world_people = _pose_candidates(frame, self.lmk, self.mp, **zoom_regions(self.tracker, self.n))
        self.people = people   # everyone found in this frame (eval/pose_models.py counts them)
        arr = np.full((33, 4), np.nan, np.float32)
        warr = np.full((33, 3), np.nan, np.float32)
        scene = cv2.resize(frame, (32, 18)).astype(float) / 255
        changed = self.previous_scene is not None and np.mean(np.abs(scene - self.previous_scene)) > .25
        self.previous_scene = scene
        looks = [signature(frame, p) for p in people]
        best = self.tracker.select(people, looks, cut=changed if cut is None else (cut or changed))
        if best is not None:
            arr = people[best]
            warr = world_people[best]
            self.tracker.last_box = box_of(arr)
            self.tracker.last_torso = float(np.linalg.norm(
                (arr[[11, 12], :2].mean(0) - arr[[23, 24], :2].mean(0)) * [self.w, self.h]))
        self.n += 1
        return arr, warr


def make_track(times: list[float], lms: list, worlds: list, fps: float, w: int, h: int, meta: dict) -> PoseTrack:
    """A PoseTrack from per-frame landmarks, with implausible bodies blanked."""
    lm_arr = np.stack(lms) if lms else np.zeros((0, 33, 4), np.float32)
    w_arr = np.stack(worlds) if worlds else np.zeros((0, 33, 3), np.float32)
    bad = implausible(lm_arr, w, h)
    lm_arr[bad] = np.nan
    w_arr[bad] = np.nan
    return PoseTrack(fps=fps, width=w, height=h, times=np.array(times), lm=lm_arr, world=w_arr,
                     meta={**meta, "rejected": int(bad.sum()), "player_id": 1})


def extract_pose(video: str | Path, stride: int = 1, num_poses: int = 3,
                 max_frames: int | None = None,
                 identity: np.ndarray | None = None) -> PoseTrack:
    """Run PoseLandmarker over every `stride`-th frame. When several people are visible,
    select the nearest initially, then retain that torso identity across cuts/occlusions."""
    import mediapipe as mp
    from mediapipe.tasks.python import vision

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    times, lms, worlds = [], [], []
    idx = 0
    with vision.PoseLandmarker.create_from_options(_landmarker_options(num_poses)) as lmk:
        follower = Follower(lmk, mp, w, h, identity)
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % stride == 0:
                arr, warr = follower.step(frame)
                times.append(idx / fps)
                lms.append(arr)
                worlds.append(warr)
                if max_frames and len(times) >= max_frames:
                    break
            idx += 1
    cap.release()
    ref = follower.tracker.reference
    return make_track(times, lms, worlds, fps / stride, w, h,
                      {"source_fps": fps, "stride": stride, "identity": ref.tolist() if ref is not None else None})


SMALL_PLAYER = 60   # px torso at the working size: below it, also search a zoomed crop
LOST = 15           # processed frames missing before searching the zoomed quarters instead
RESEARCH_EVERY = 10  # ...on every this many processed frames while lost


def zoom_regions(tracker, n: int) -> dict:
    """Extra crops for _pose_candidates when the selected player is small or was missed:
    around where they were (2.5x their box), or the zoomed quarters once they are long lost.
    A far-side player is too small for the full or half frame (IMG_8782's opponent was
    seen in 3% of frames without this)."""
    if tracker.reference is None:
        return {}
    if tracker.last_box is None or tracker.missing >= LOST:
        # Not found yet (a tapped far player can be missed from the first frame) or long lost:
        # search the zoomed quarters, every frame at first, then every RESEARCH_EVERY frames.
        return {"extra": QUARTERS} if n < 5 or n % RESEARCH_EVERY == 0 else {}
    if tracker.missing == 0 and tracker.last_torso >= SMALL_PLAYER:
        return {}
    x0, y0, x1, y1 = tracker.last_box
    cx, cy, bw, bh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * 2.5, (y1 - y0) * 2.5
    side = max(bw, bh * 9 / 16)   # roughly square in pixels on a 16:9 frame
    return {"first": [(max(0., cx - side / 2), max(0., cy - bh / 2), min(1., cx + side / 2), min(1., cy + bh / 2))]}


def initial_identity(video: str | Path) -> np.ndarray | None:
    """Select the person nearest the camera most often across the whole video (see
    identity.choose_seed for the fallback when that vote is ambiguous)."""
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    from .identity import appearance, choose_seed, signature

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {video}")
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    looks, signatures = [], []
    opts = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path())),
        running_mode=vision.RunningMode.IMAGE, num_poses=3,
        min_pose_detection_confidence=0.4, min_tracking_confidence=0.4,
    )
    try:
        with vision.PoseLandmarker.create_from_options(opts) as landmarker:
            for index in np.linspace(0, max(0, count - 1), min(24, count), dtype=int):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
                ok, frame = cap.read()
                if not ok:
                    continue
                h, w = frame.shape[:2]
                if h > 720:
                    frame = cv2.resize(frame, (round(w * 720 / h), 720))
                people, _ = _pose_candidates(frame, landmarker, mp)
                if people:
                    h, w = frame.shape[:2]
                    near = max(people, key=lambda p: np.linalg.norm(
                        (p[[11, 12], :2].mean(0) - p[[23, 24], :2].mean(0)) * [w, h]))
                    looks.append(appearance(frame, near))
                    signatures.append(signature(frame, near))
    finally:
        cap.release()
    # None when nobody was seen: the existing require_player check gives the no-player message.
    return choose_seed(looks, signatures)


def _overlap(a: tuple, b: tuple) -> float:
    """Intersection over union of two normalised (x0, y0, x1, y1) boxes."""
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - w * h
    return w * h / union if union > 0 else 0.0


def identity_from_box(video: str | Path, time: float, box: tuple[float, float, float, float]) -> np.ndarray:
    """The tracker seed for the player the user tapped: the appearance of the person at `time`
    whose body box overlaps `box` most. Raises NoPlayer when nobody is there."""
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    from .identity import signature
    from .people import box_of

    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, time) * 1000)
    ok, frame = cap.read()
    cap.release()
    when = f"{int(time // 60)}:{int(time % 60):02d}"
    if not ok:
        raise NoPlayer(f"We couldn't read the video at {when}, where you picked the player. Pick again.")
    h, w = frame.shape[:2]
    if h > 720:   # the working size of detection and tracking
        frame = cv2.resize(frame, (round(w * 720 / h), 720))
    opts = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path())),
        running_mode=vision.RunningMode.IMAGE, num_poses=3,
        min_pose_detection_confidence=0.4, min_tracking_confidence=0.4,
    )
    with vision.PoseLandmarker.create_from_options(opts) as landmarker:
        people, _ = _pose_candidates(frame, landmarker, mp, extra=QUARTERS)
    scored = []
    for p in people:
        hx, hy = p[[23, 24], :2].mean(0)
        inside = box[0] <= hx <= box[2] and box[1] <= hy <= box[3]
        scored.append((_overlap(box_of(p), box) + inside, p))
    best = max(scored, key=lambda x: x[0], default=(0.0, None))
    if best[0] < .3:
        raise NoPlayer(f"We couldn't find the player you picked at {when}. Pick again, or trim the video.")
    return signature(frame, best[1])


def player_thumb(video: str | Path, track: PoseTrack, i: int | None = None) -> str | None:
    """A small JPEG (data URL) of the tracked player at frame i (default: their first seen frame),
    for the result page's "who we analysed"."""
    from .people import _thumb, box_of

    seen = np.flatnonzero(track.valid)
    if not len(seen):
        return None
    i = int(i) if i is not None and track.valid[int(i)] else int(seen[0])
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_MSEC, float(track.times[i]) * 1000)
    ok, frame = cap.read()
    cap.release()
    return _thumb(frame, box_of(track.lm[i])) if ok else None


def save_track(track: PoseTrack, path: str | Path) -> None:
    np.savez_compressed(path, fps=track.fps, width=track.width, height=track.height,
                        times=track.times, lm=track.lm, world=track.world,
                        stride=track.meta.get("stride", 1))


def load_track(path: str | Path) -> PoseTrack:
    d = np.load(path)
    return PoseTrack(fps=float(d["fps"]), width=int(d["width"]), height=int(d["height"]),
                     times=d["times"], lm=d["lm"], world=d["world"], meta={"stride": int(d["stride"])})


# Head-to-feet height in torso lengths. Real players measured 2.7-3.2 on the sample frames
# (standing ~3, crouched or leaning 2+). Table-base phantoms on the 720p coaching demo: 0.87
# (it won the seed vote's first frame), 1.5 and 1.7, all with full visibility.
MIN_BODY_SPAN = 2.0


def implausible(lm: np.ndarray, w: int, h: int) -> np.ndarray:
    """Flag garbage detections (e.g. a 'lying down' skeleton on a table edge): the torso
    must be roughly upright, not tiny compared with the median torso, and carry a body
    that is taller than the torso alone."""
    if len(lm) == 0:
        return np.zeros(0, bool)
    xy = lm[:, :, :2] * np.array([w, h])
    sh = (xy[:, L_SHOULDER] + xy[:, R_SHOULDER]) / 2
    hp = (xy[:, L_HIP] + xy[:, R_HIP]) / 2
    v = hp - sh
    length = np.linalg.norm(v, axis=1)
    upright = v[:, 1] > 0.5 * length            # hips below shoulders, < ~60 deg lean
    med = np.nanmedian(length) if np.isfinite(length).any() else 0
    big_enough = length > 0.4 * med
    span = xy[:, :, 1].max(axis=1) - xy[:, :, 1].min(axis=1)
    whole = span >= MIN_BODY_SPAN * length
    ok = upright & big_enough & whole
    return ~ok & np.isfinite(length)


# ---------------------------------------------------------------- analysis helpers

def _interp_nan(a: np.ndarray) -> np.ndarray:
    a = a.copy()
    flat = a.reshape(len(a), -1)
    t = np.arange(len(a))
    for j in range(flat.shape[1]):
        col = flat[:, j]
        m = ~np.isnan(col)
        if m.sum() >= 2:
            col[~m] = np.interp(t[~m], t[m], col[m])
        elif m.sum() == 1:
            col[~m] = col[m][0]
    return flat.reshape(a.shape)


def _angle(a, b, c) -> np.ndarray:
    """Angle at b (degrees) for arrays of points (...,2|3)."""
    ba, bc = a - b, c - b
    cos = (ba * bc).sum(-1) / (np.linalg.norm(ba, axis=-1) * np.linalg.norm(bc, axis=-1) + 1e-9)
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def wrist_speeds(track: PoseTrack) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (left_speed, right_speed, torso_len_px), speeds in torso-lengths per second."""
    if len(track.times) < 3:
        z = np.zeros(len(track.times))
        return z, z, z + 1
    xy = _interp_nan(track.lm[:, :, :2]) * np.array([track.width, track.height])
    sh = (xy[:, L_SHOULDER] + xy[:, R_SHOULDER]) / 2
    hp = (xy[:, L_HIP] + xy[:, R_HIP]) / 2
    torso = np.median(np.linalg.norm(sh - hp, axis=1)) + 1e-6
    reliable = track.valid.copy()
    reliable[1:] &= track.valid[:-1]
    reliable[:-1] &= track.valid[1:]
    jumps = np.linalg.norm(np.diff(hp, axis=0), axis=1) > torso
    reliable[1:] &= ~jumps
    reliable[:-1] &= ~jumps
    out = []
    for wi in (L_WRIST, R_WRIST):
        # wrist relative to body centre, so walking doesn't count as swinging
        rel = xy[:, wi] - (sh + hp) / 2
        v = np.linalg.norm(np.gradient(rel, axis=0), axis=1) * track.fps / torso
        v = uniform_filter1d(np.nan_to_num(v), size=max(1, int(track.fps * 0.1)))
        v[~reliable | (track.lm[:, wi, 3] < .5)] = 0
        out.append(v)
    return out[0], out[1], np.full(len(xy), torso)


def dominant_side(track: PoseTrack) -> str:
    l, r, _ = wrist_speeds(track)
    if len(l) == 0:
        return "unknown"
    pl, pr = np.percentile(l, 95), np.percentile(r, 95)
    if max(pl, pr) < 1e-6 or abs(pl - pr) / max(pl, pr) < 0.1:
        return "unknown"
    return "right" if pr > pl else "left"


def paddle_scores(video: str | Path, track: PoseTrack, every: int = 4) -> dict:
    """Count red-rubber pixels around each wrist over sampled frames. The bat hand holds
    the paddle, so this is a stronger cue than swing speed (the free arm also swings,
    and walking between points moves both arms)."""
    if len(track.times) == 0:
        return {"left": 0, "right": 0}
    xy = _interp_nan(track.lm[:, :, :2]) * np.array([track.width, track.height])
    torso = np.median(np.linalg.norm((xy[:, L_SHOULDER] + xy[:, R_SHOULDER]) / 2
                                     - (xy[:, L_HIP] + xy[:, R_HIP]) / 2, axis=1))
    r = max(12, int(torso * 0.45))
    cap = cv2.VideoCapture(str(video))
    scores = {"left": 0, "right": 0}
    i = 0
    while i < len(track.times):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i * int(track.meta.get("stride", 1)))
        ok, frame = cap.read()
        if not ok:
            break
        if track.valid[i]:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            red = (((hsv[..., 0] < 10) | (hsv[..., 0] > 170)) & (hsv[..., 1] > 110)
                   & (hsv[..., 2] > 60))
            for side, wi in (("left", L_WRIST), ("right", R_WRIST)):
                x, y = xy[i, wi].astype(int)
                scores[side] += int(red[max(0, y - r):y + r, max(0, x - r):x + r].sum())
        i += every
    cap.release()
    return scores


def contact_side(track: PoseTrack, hit_times: list[float]) -> str:
    """Vote for the visible wrist moving faster just before/around audio contacts."""
    left, right, _ = wrist_speeds(track)
    votes = []
    for t in hit_times:
        indices = np.flatnonzero((track.times >= t - .12) & (track.times <= t + .06))
        indices = indices[(indices > 0) & (indices < len(track.times) - 1)]
        good = [i for i in indices if track.valid[i-1:i+2].all()
                and np.min(track.lm[i-1:i+2, [L_WRIST, R_WRIST], 3]) >= .5]
        if not good:
            continue
        l, r = float(np.max(left[good])), float(np.max(right[good]))
        if max(l, r) >= 1. and max(l, r) > 1.35 * max(min(l, r), .1):
            votes.append(1 if r > l else -1)
    if len(votes) < 2 or abs(sum(votes)) / len(votes) < .5:
        return "unknown"
    return "right" if sum(votes) > 0 else "left"


def bat_side(video: str | Path, track: PoseTrack, hand: str = "auto",
             trust_hand: bool = False, hit_times: list[float] | None = None,
             assume: str | None = None, pooled: dict | None = None) -> tuple[str, str]:
    """Pick the bat arm (as a MediaPipe side label). Returns (side, how).
    Order: paddle colour near a wrist (when clearly one-sided) > the user's --hand > the
    faster wrist. trust_hand: `hand` is known (a roster pro), so it wins outright; red
    arena furniture next to the free hand can fool the paddle colour.
    pooled: red-rubber pixels per wrist summed over several rallies (choose_window's scans),
    used when this window's own cues and the user's hand don't decide.
    assume: the hand to state as an assumption when no cue is decisive, for callers that
    can't ask the user (Coach has no hand field). Without it, the user is asked to choose."""
    if trust_hand and hand in ("left", "right"):
        return hand, "known"
    if hand == "auto" and hit_times:
        contact = contact_side(track, hit_times)
        if contact != "unknown":
            return contact, "wrist motion near audio contacts"
    sc = paddle_scores(video, track)
    lo, hi = sorted(sc.values())
    if hi > 2000 and hi > 1.8 * max(lo, 1):
        return max(sc, key=sc.get), f"paddle colour near wrist {sc}"
    if hand in ("left", "right"):
        return hand, "user"
    if pooled:
        lo, hi = sorted(pooled.values())
        if hi > 2000 and hi > 1.8 * max(lo, 1):
            return max(pooled, key=pooled.get), f"paddle colour over several rallies {pooled}"
    side = dominant_side(track)
    if side == "unknown" and assume in ("left", "right"):
        return assume, f"assumed {assume}-handed: no clear bat-hand cue in this clip"
    if side == "unknown":
        raise NoPlayer("We couldn't tell your hitting hand. Choose left or right, or upload a clearer swing.")
    return side, "faster wrist (no decisive contact evidence)"


def swing_peaks(track: PoseTrack, side: str | None = None, min_gap_s: float = 0.5) -> np.ndarray:
    """Frame indices of swing peaks (max wrist speed of the bat hand)."""
    side = side or dominant_side(track)
    l, r, _ = wrist_speeds(track)
    v = r if side != "left" else l
    if len(v) < 5:
        return np.array([], int)
    thr = max(np.percentile(v, 75), 0.5 * np.percentile(v, 99))
    pk, _ = find_peaks(v, height=thr, distance=max(1, int(min_gap_s * track.fps)))
    return pk


def best_window(track: PoseTrack, seconds: float = 6.0) -> tuple[float, float]:
    """Pick the window with the most bat-hand swing energy where the player is visible."""
    if len(track.times) == 0:
        return 0.0, seconds
    dur = track.times[-1]
    if dur <= seconds:
        return 0.0, float(dur)
    l, r, _ = wrist_speeds(track)
    v = np.maximum(l, r) * track.valid
    n = max(1, int(seconds * track.fps))
    energy = np.convolve(v, np.ones(n), "valid")
    i = int(np.argmax(energy))
    return float(track.times[i]), float(track.times[min(i + n, len(track.times) - 1)])


def pose_metrics(track: PoseTrack, i: int, side: str) -> dict:
    """Human-readable body metrics at frame i (used by the offline analyzer and as LLM context)."""
    from .strokes import _points

    xy = _interp_nan(track.lm[:, :, :2])[i] * np.array([track.width, track.height])
    # Angles and widths from 3D world points when MediaPipe gives them (like players/body.py):
    # in pixels, shoulders seen edge-on made a stance read as 6.4x shoulder width.
    p = _points(track)[i]
    s = (R_SHOULDER, R_ELBOW, R_WRIST) if side != "left" else (L_SHOULDER, L_ELBOW, L_WRIST)
    elbow = float(_angle(p[s[0]], p[s[1]], p[s[2]]))
    knee = float(np.mean([_angle(p[L_HIP], p[L_KNEE], p[L_ANKLE]),
                          _angle(p[R_HIP], p[R_KNEE], p[R_ANKLE])]))
    sh_w = np.linalg.norm(p[L_SHOULDER] - p[R_SHOULDER]) + 1e-6
    ft_w = np.linalg.norm(p[L_ANKLE] - p[R_ANKLE])
    sh_y = (xy[L_SHOULDER, 1] + xy[R_SHOULDER, 1]) / 2
    hp_y = (xy[L_HIP, 1] + xy[R_HIP, 1]) / 2
    wy = xy[s[2], 1]
    rel_h = (hp_y - wy) / (hp_y - sh_y + 1e-6)  # 0 = hip height, 1 = shoulder height
    # Out-of-frame joints are guessed by MediaPipe (a close camera cut at the waist read as
    # "knees 79 deg"); say nothing about joints we cannot see.
    seen = lambda *j: bool(np.nan_to_num(track.lm[i, list(j), 3]).min() >= MIN_JOINT_VIS)
    legs = seen(L_KNEE, R_KNEE, L_ANKLE, R_ANKLE)
    return {
        "t": round(float(track.times[i]), 2),
        "elbow_angle_deg": round(elbow) if seen(*s) else None,
        "knee_angle_deg": round(knee) if legs else None,
        "stance_width_x_shoulders": round(float(ft_w / sh_w), 2) if legs else None,
        "wrist_height_hip0_shoulder1": round(float(rel_h), 2) if seen(s[2]) else None,
    }


MIN_JOINT_VIS = 0.5


def whole_body(track: PoseTrack) -> np.ndarray:
    """Frames with the selected player and their knees and ankles in frame."""
    legs = np.nan_to_num(track.lm[:, [L_KNEE, R_KNEE, L_ANKLE, R_ANKLE], 3]).min(axis=1)
    return track.valid & (legs >= MIN_JOINT_VIS)


def summarize(track: PoseTrack, side: str | None = None, peaks: list[int] | None = None) -> dict:
    """peaks: the swings to report (pipeline.real_strokes); default every wrist-speed peak."""
    side = side or dominant_side(track)
    pk = swing_peaks(track, side) if peaks is None else np.asarray(peaks, int)
    return {
        "frames": int(len(track.times)),
        "person_visible_ratio": round(float(track.valid.mean()) if len(track.times) else 0.0, 2),
        "bat_hand": side,
        "swing_count": int(len(pk)),
        "swings": [pose_metrics(track, int(i), side) for i in pk[:12]],
    }
