"""Phase 2 (eval only): MediaPipe + our appearance tracker vs a multi-person pose model with
ByteTrack (rtmlib's RTMPose or RTMO on ONNX Runtime, CPU), on the same frames of the same clips.

Measures, per model and clip:
- speed: seconds per frame (detection + pose + tracking) at 720p;
- far-player coverage: in rally frames (from the sound), the share where a second, smaller
  person (the far player) is found with shoulders and hips;
- identity: the followed player's hips inside the hand-checked box at the audited times
  (eval/regressions/*_identity.json), seeded from the first audited box like a tap;
- strokes: at audio hits inside rallies, how often the bat wrist is seen around contact and the
  elbow/knee angles at the wrist-speed peak (compared across models).

Two virtual environments, because rtmlib's OpenCV build and MediaPipe don't share one. The
second is git-ignored and made with
    python3 -m venv eval/work/venv-pose && eval/work/venv-pose/bin/pip install rtmlib onnxruntime scipy
(rtmlib downloads its ONNX models to ~/.cache/rtmlib on first use: ~320 MB.)
    .venv/bin/python -m eval.pose_models run mediapipe IMG_8782
    eval/work/venv-pose/bin/python eval/pose_models.py run rtmpose IMG_8782   (also: rtmo)
    ... strokes <model> IMG_8782   (30 fps around 4 of the user's strokes)
    ... bench <model>              (s/frame on the same 150 frames, nothing else running)
    .venv/bin/python -m eval.pose_models score
Outputs go to eval/work/pose_models/ (git-ignored); `score` prints the table and writes
eval/pose_models_results.json."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent / "work" / "pose_models"
FPS = 5.0          # the whole video, like a tracker between strokes (production uses 2 fps there)
CLIPS = {
    "IMG_8782": {"video": "samples/IMG_8782.MOV", "audit": "eval/regressions/img8782_identity.json"},
    "match_b": {"video": "samples/match_b.mp4", "audit": "eval/regressions/match_b_identity.json"},
}
# MediaPipe's 33 landmarks -> the 17 COCO keypoints rtmlib returns (same order as COCO).
MP_TO_COCO = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
L_SH, R_SH, L_EL, R_EL, L_WR, R_WR, L_HIP, R_HIP, L_KN, R_KN, L_AN, R_AN = 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16


def frames(video: Path, fps: float, height: int = 720):
    """(time, BGR frame) at `fps`, at most `height` px high, from one ffmpeg pipe."""
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:stream_side_data=rotation",
         "-of", "json", str(video)], check=True, capture_output=True, text=True).stdout)["streams"][0]
    w, h = probe["width"], probe["height"]
    if any(abs(int(d.get("rotation", 0))) in (90, 270) for d in probe.get("side_data_list", [])):
        w, h = h, w
    if h > height:
        w, h = round(w * height / h / 2) * 2, height
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={fps},scale={w}:{h}",
                             "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    i = 0
    try:
        while True:
            buf = proc.stdout.read(w * h * 3)
            if len(buf) < w * h * 3:
                break
            yield i / fps, np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            i += 1
    finally:
        proc.kill()
        proc.wait()


def iou(a, b) -> float:
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - w * h
    return w * h / u if u > 0 else 0.0


class ByteTrack:
    """ByteTrack's association (Zhang et al. 2022) without the Kalman filter: high-score
    detections matched to tracks by IoU first (Hungarian), then leftover tracks to low-score
    ones; unmatched high ones start tracks; tracks lost for `max_lost` frames end. Boxes move
    with a constant-velocity guess."""

    def __init__(self, high: float = .5, low: float = .1, match: float = .2, max_lost: int = 10):
        self.high, self.low, self.match, self.max_lost = high, low, match, max_lost
        self.tracks: dict[int, dict] = {}
        self.next = 1

    def update(self, boxes: np.ndarray, scores: np.ndarray) -> dict[int, int]:
        from scipy.optimize import linear_sum_assignment

        for t in self.tracks.values():
            t["pred"] = t["box"] + t["vel"]
        assigned: dict[int, int] = {}
        free = list(self.tracks)
        for tier in (np.flatnonzero(scores >= self.high), np.flatnonzero((scores >= self.low) & (scores < self.high))):
            if not len(tier) or not free:
                continue
            cost = np.array([[1 - iou(self.tracks[t]["pred"], boxes[d]) for d in tier] for t in free])
            rows, cols = linear_sum_assignment(cost)
            for r, c in zip(rows, cols):
                if cost[r, c] <= 1 - self.match:
                    assigned[free[r]] = int(tier[c])
            free = [t for t in free if t not in assigned]
        for tid, d in assigned.items():
            t = self.tracks[tid]
            t["vel"] = 0.5 * t["vel"] + 0.5 * (boxes[d] - t["box"])
            t["box"], t["lost"] = boxes[d].astype(float), 0
        for tid in free:
            self.tracks[tid]["lost"] += 1
            self.tracks[tid]["box"] = self.tracks[tid]["pred"]
        for tid in [t for t, v in self.tracks.items() if v["lost"] > self.max_lost]:
            del self.tracks[tid]
        used = set(assigned.values())
        for d in np.flatnonzero(scores >= self.high):
            if int(d) not in used:
                self.tracks[self.next] = {"box": boxes[d].astype(float), "vel": np.zeros(4), "lost": 0}
                assigned[self.next] = int(d)
                self.next += 1
        return assigned


MODELS = ("mediapipe", "rtmpose", "rtmpose-lite", "rtmo")


def estimator(model: str):
    """rtmpose: YOLOX-m + RTMPose-m (rtmlib 'balanced'); rtmpose-lite: YOLOX-tiny + RTMPose-s
    ('lightweight'); rtmo: RTMO-m, one stage (detection and keypoints together, like YOLO-pose)."""
    from rtmlib import RTMO, Body

    if model == "rtmo":
        return RTMO("https://download.openmmlab.com/mmpose/v1/projects/rtmo/onnx_sdk/"
                    "rtmo-m_16xb16-600e_body7-640x640-39e78cc4_20231211.zip", backend="onnxruntime", device="cpu")
    return Body(mode="lightweight" if model == "rtmpose-lite" else "balanced", backend="onnxruntime", device="cpu")


def run_rtm(model: str, clip: str) -> None:
    """RTMPose (YOLOX detector + RTMPose, rtmlib 'balanced') or RTMO (one stage), + ByteTrack.
    The followed track is the one on the first audited box; when it ends, the nearest new
    track to its last box takes over (no appearance model: what identity errors measure)."""
    est = estimator(model)
    audit = json.loads((ROOT / "backend" / CLIPS[clip]["audit"]).read_text())
    seed_t, seed_box = audit["frames"][0]["time"], audit["frames"][0]["box"]
    bt = ByteTrack()
    out = {"times": [], "secs": [], "people": [], "followed": [], "kp": [], "boxes": []}
    me = None
    for t, frame in frames(ROOT / CLIPS[clip]["video"], FPS):
        h, w = frame.shape[:2]
        begin = time.monotonic()
        kps, scores = est(frame)
        kps, scores = np.asarray(kps, float).reshape(-1, 17, 2), np.asarray(scores, float).reshape(-1, 17)
        conf = scores.mean(1) if len(scores) else np.zeros(0)
        boxes = np.array([[k[:, 0].min() / w, k[:, 1].min() / h, k[:, 0].max() / w, k[:, 1].max() / h] for k in kps]).reshape(-1, 4)
        ids = bt.update(boxes, np.clip(conf, 0, 1))
        secs = time.monotonic() - begin
        if me is None and t >= seed_t - 1e-6:   # the tap: the person whose hips are in the box
            best = [(tid, d) for tid, d in ids.items() if _hips_in(kps[d], scores[d], w, h, seed_box)]
            me = best[0][0] if best else None
        elif me is not None and me not in bt.tracks:   # lost: hand over to the closest new track
            last = out["boxes"][-1] if out["boxes"] and out["boxes"][-1] is not None else None
            cand = [(iou(last, boxes[d]) if last is not None else 0, tid) for tid, d in ids.items()]
            me = max(cand)[1] if cand else None
        d = ids.get(me) if me is not None else None
        kp = np.concatenate([kps[d] / [w, h], scores[d][:, None]], 1) if d is not None else np.full((17, 3), np.nan)
        out["times"].append(t)
        out["secs"].append(secs)
        out["people"].append(_people(kps, scores, w, h))
        out["followed"].append(d is not None)
        out["kp"].append(kp)
        out["boxes"].append(boxes[d] if d is not None else None)
    _save(model, clip, out)


def run_mediapipe(clip: str) -> None:
    """The production tracker: pose._pose_candidates (half-frame crops, zoom) + PlayerIdentity,
    seeded by pose.identity_from_box at the first audited box (as a tap does)."""
    import mediapipe as mp
    from mediapipe.tasks.python import vision

    from technique import pose

    audit = json.loads((ROOT / "backend" / CLIPS[clip]["audit"]).read_text())
    video = ROOT / CLIPS[clip]["video"]
    seed = pose.identity_from_box(video, audit["frames"][0]["time"], tuple(audit["frames"][0]["box"]))
    out = {"times": [], "secs": [], "people": [], "followed": [], "kp": [], "boxes": []}
    with vision.PoseLandmarker.create_from_options(pose._landmarker_options()) as lmk:
        follower = None
        for t, frame in frames(video, FPS):
            h, w = frame.shape[:2]
            if follower is None:
                follower = pose.Follower(lmk, mp, w, h, seed)
            begin = time.monotonic()
            arr, _ = follower.step(frame)
            secs = time.monotonic() - begin
            kp = np.full((17, 3), np.nan) if np.isnan(arr[0, 0]) else np.concatenate([arr[MP_TO_COCO, :2], arr[MP_TO_COCO, 3:4]], 1)
            out["times"].append(t)
            out["secs"].append(secs)
            out["people"].append(_people([p[MP_TO_COCO, :2] * [w, h] for p in follower.people],
                                         [p[MP_TO_COCO, 3] for p in follower.people], w, h))
            out["followed"].append(not np.isnan(arr[0, 0]))
            out["kp"].append(kp)
            out["boxes"].append(None)
    _save("mediapipe", clip, out)


def _hips_in(kp, sc, w, h, box) -> bool:
    hx, hy = kp[[L_HIP, R_HIP]].mean(0) / [w, h]
    return box[0] <= hx <= box[2] and box[1] <= hy <= box[3]


def _people(kps, scores, w, h) -> list:
    """Each person with shoulders and hips seen: (torso length as a frame share, hip x, hip y)."""
    out = []
    for k, s in zip(kps, scores):
        if s[[L_SH, R_SH, L_HIP, R_HIP]].min() < .3:
            continue
        sh, hp = k[[L_SH, R_SH]].mean(0) / [w, h], k[[L_HIP, R_HIP]].mean(0) / [w, h]
        out.append([float(np.linalg.norm((sh - hp) * [w / h, 1])), float(hp[0]), float(hp[1])])
    return out


def _save(model: str, clip: str, out: dict) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(WORK / f"{model}-{clip}.npz", times=np.array(out["times"]), secs=np.array(out["secs"]),
                        followed=np.array(out["followed"]), kp=np.array(out["kp"], float),
                        people=np.array(json.dumps(out["people"])))
    print(f"{model} {clip}: {len(out['times'])} frames, {np.mean(out['secs']):.3f} s/frame, "
          f"followed {np.mean(out['followed']):.2f}")


# Four of the user's strokes in IMG_8782 (Phase 1's probes: bat wrist >= 5 torso/s at the sound).
STROKES = {"IMG_8782": [63.76, 65.54, 187.45, 189.88]}
HALF = 0.6


def _segment(video: Path, start: float, end: float, height: int):
    import cv2

    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    t = start
    while t < end:
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        if h > height:
            frame = cv2.resize(frame, (round(w * height / h / 2) * 2, height))
        yield t, frame
        t += 1 / fps
    cap.release()


def run_strokes(model: str, clip: str) -> None:
    """Full-rate pose on each stroke window; the followed person is the one MediaPipe's seed
    picks (mediapipe) or the biggest person in the window's first frame (rtm: IMG_8782's user
    is always the near player)."""
    video = ROOT / CLIPS[clip]["video"]
    res = []
    if model == "mediapipe":
        import mediapipe as mp
        from mediapipe.tasks.python import vision

        from technique import pose
        audit = json.loads((ROOT / "backend" / CLIPS[clip]["audit"]).read_text())
        seed = pose.identity_from_box(video, audit["frames"][0]["time"], tuple(audit["frames"][0]["box"]))
        with vision.PoseLandmarker.create_from_options(pose._landmarker_options()) as lmk:
            for hit in STROKES[clip]:
                follower, kps, ts, secs = None, [], [], []
                for t, frame in _segment(video, hit - HALF, hit + HALF, 720):
                    h, w = frame.shape[:2]
                    follower = follower or pose.Follower(lmk, mp, w, h, seed)
                    b = time.monotonic()
                    arr, _ = follower.step(frame)
                    secs.append(time.monotonic() - b)
                    kps.append(np.full((17, 3), np.nan) if np.isnan(arr[0, 0])
                               else np.concatenate([arr[MP_TO_COCO, :2], arr[MP_TO_COCO, 3:4]], 1))
                    ts.append(t)
                res.append({"hit": hit, "times": ts, "kp": np.array(kps).tolist(), "secs": secs, "size": [w, h]})
    else:
        est = estimator(model)
        for hit in STROKES[clip]:
            bt, me, kps, ts, secs = ByteTrack(), None, [], [], []
            for t, frame in _segment(video, hit - HALF, hit + HALF, 720):
                h, w = frame.shape[:2]
                b = time.monotonic()
                k, sc = est(frame)
                k, sc = np.asarray(k, float).reshape(-1, 17, 2), np.asarray(sc, float).reshape(-1, 17)
                boxes = np.array([[q[:, 0].min() / w, q[:, 1].min() / h, q[:, 0].max() / w, q[:, 1].max() / h] for q in k]).reshape(-1, 4)
                ids = bt.update(boxes, np.clip(sc.mean(1) if len(sc) else np.zeros(0), 0, 1))
                secs.append(time.monotonic() - b)
                if me is None and ids:
                    me = max(ids, key=lambda tid: (boxes[ids[tid], 3] - boxes[ids[tid], 1]))
                d = ids.get(me)
                kps.append(np.concatenate([k[d] / [w, h], sc[d][:, None]], 1) if d is not None else np.full((17, 3), np.nan))
                ts.append(t)
            res.append({"hit": hit, "times": ts, "kp": np.array(kps).tolist(), "secs": secs, "size": [w, h]})
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / f"strokes-{model}-{clip}.json").write_text(json.dumps(res))
    print(f"{model} strokes {clip}: {sum(len(r['times']) for r in res)} frames, {np.mean([s for r in res for s in r['secs']]):.3f} s/frame")


def _angle(a, b, c) -> float:
    v1, v2 = a - b, c - b
    return float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9), -1, 1))))


def stroke_metrics(windows: list[dict], side: str = "right") -> list[dict]:
    """Per window: bat wrist seen (conf >= .5) share, peak wrist speed near the hit (torso/s),
    elbow and knee angle at that peak."""
    wr, el, sh, hp = (R_WR, R_EL, R_SH, R_HIP) if side == "right" else (L_WR, L_EL, L_SH, L_HIP)
    out = []
    for r in windows:
        kp, t = np.array(r["kp"], float), np.array(r["times"])
        w, h = r["size"]
        xy = kp[:, :, :2] * [w, h]
        seen = kp[:, wr, 2] >= .5
        centre = (xy[:, L_SH] + xy[:, R_SH] + xy[:, L_HIP] + xy[:, R_HIP]) / 4
        torso = np.nanmedian(np.linalg.norm((xy[:, L_SH] + xy[:, R_SH]) / 2 - (xy[:, L_HIP] + xy[:, R_HIP]) / 2, axis=1))
        rel = xy[:, wr] - centre
        v = np.linalg.norm(np.gradient(rel, axis=0), axis=1) * 30 / (torso or 1)
        v[~seen] = np.nan
        near = np.flatnonzero(np.abs(t - r["hit"]) <= .15)
        i = int(near[np.nanargmax(v[near])]) if len(near) and not np.isnan(v[near]).all() else None
        m = {"hit": r["hit"], "wrist_seen": round(float(seen.mean()), 2),
             "peak_speed": round(float(v[i]), 1) if i is not None else None}
        if i is not None:
            p = xy[i]
            m["elbow"] = round(_angle(p[sh], p[el], p[wr]))
            m["knee"] = round((_angle(p[L_HIP], p[L_KN], p[L_AN]) + _angle(p[R_HIP], p[R_KN], p[R_AN])) / 2)
        out.append(m)
    return out


def score() -> dict:
    """The comparison table (main venv: uses the audio rallies)."""
    from app.rally import detect_rallies
    import tempfile

    results: dict = {}
    for clip, info in CLIPS.items():
        rallies = detect_rallies(ROOT / info["video"], Path(tempfile.mkdtemp()), 3.0, 1.6, 4)
        audit = json.loads((ROOT / "backend" / info["audit"]).read_text())
        for model in MODELS:
            f = WORK / f"{model}-{clip}.npz"
            if not f.exists():
                continue
            d = np.load(f)
            times, kp, people = d["times"], d["kp"], json.loads(str(d["people"]))
            in_play = np.array([any(r.start <= t <= r.end for r in rallies) for t in times])
            # The far player: a second person whose torso is under 0.7x the biggest one's.
            far = [len(p) >= 2 and sorted(q[0] for q in p)[-2] < .7 * max(q[0] for q in p) for p in people]
            ident = {"correct": 0, "wrong": 0, "missing": 0}
            for fr in audit["frames"][1:]:
                i = int(np.argmin(np.abs(times - fr["time"])))
                if np.isnan(kp[i, L_HIP, 0]):
                    ident["missing"] += 1
                    continue
                hx, hy = kp[i, [L_HIP, R_HIP], :2].mean(0)
                b = fr["box"]
                pad = .03
                ok = b[0] - pad <= hx <= b[2] + pad and b[1] - pad <= hy <= b[3] + pad
                ident["correct" if ok else "wrong"] += 1
            row = {"s_per_frame": round(float(d["secs"].mean()), 3), "frames": int(len(times)),
                   "followed": round(float(d["followed"].mean()), 2),
                   "far_coverage_in_play": round(float(np.mean([f_ for f_, p in zip(far, in_play) if p])), 2),
                   "two_people_in_play": round(float(np.mean([len(p) >= 2 for p, q in zip(people, in_play) if q])), 2),
                   "identity": ident}
            s = WORK / f"strokes-{model}-{clip}.json"
            if s.exists():
                row["strokes"] = stroke_metrics(json.loads(s.read_text()))
                row["stroke_s_per_frame"] = round(float(np.mean([x for r in json.loads(s.read_text()) for x in r["secs"]])), 3)
            b = WORK / f"bench-{model}.json"
            if b.exists():
                row["bench_s_per_frame"] = json.loads(b.read_text())["s_per_frame"]
            results.setdefault(clip, {})[model] = row
    (Path(__file__).resolve().parent / "pose_models_results.json").write_text(json.dumps(results, indent=1))
    print(json.dumps(results, indent=1))
    return results


def bench(model: str, clip: str = "IMG_8782", start: float = 60.0, n: int = 150) -> None:
    """Seconds per frame on the same n frames (5 fps from `start`), run alone: the speeds from
    the full runs were taken with other work on the machine."""
    video = ROOT / CLIPS[clip]["video"]
    shots = []
    for t, frame in frames(video, FPS):
        if t >= start:
            shots.append(frame.copy())
        if len(shots) >= n:
            break
    h, w = shots[0].shape[:2]
    if model == "mediapipe":
        import mediapipe as mp
        from mediapipe.tasks.python import vision

        from technique import pose
        with vision.PoseLandmarker.create_from_options(pose._landmarker_options()) as lmk:
            f = pose.Follower(lmk, mp, w, h, None)
            f.step(shots[0])   # warm up
            b = time.monotonic()
            for im in shots:
                f.step(im)
    else:
        est, bt = estimator(model), ByteTrack()
        est(shots[0])
        b = time.monotonic()
        for im in shots:
            k, sc = est(im)
            k, sc = np.asarray(k, float).reshape(-1, 17, 2), np.asarray(sc, float).reshape(-1, 17)
            boxes = np.array([[q[:, 0].min() / w, q[:, 1].min() / h, q[:, 0].max() / w, q[:, 1].max() / h] for q in k]).reshape(-1, 4)
            bt.update(boxes, np.clip(sc.mean(1) if len(sc) else np.zeros(0), 0, 1))
    secs = (time.monotonic() - b) / len(shots)
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / f"bench-{model}.json").write_text(json.dumps({"model": model, "frames": len(shots), "s_per_frame": round(secs, 4),
                                                           "size": [w, h]}))
    print(f"bench {model}: {secs:.3f} s/frame on {len(shots)} frames {w}x{h}")


if __name__ == "__main__":
    if sys.argv[1] == "bench":
        bench(sys.argv[2])
    if sys.argv[1] == "run":
        model, clip = sys.argv[2], sys.argv[3]
        run_mediapipe(clip) if model == "mediapipe" else run_rtm(model, clip)
    elif sys.argv[1] == "strokes":
        run_strokes(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "score":
        score()
