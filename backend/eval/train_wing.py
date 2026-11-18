"""1b and 1c: learned stroke classifiers with an abstain threshold, trained on calibration
contact windows only, frozen, then scored once on the pre-declared validation videos
(eval/geometry_protocol.json: validation test_6 and test_3; gates: selective precision >= 0.9,
no class's recall drops more than 0.05 against the baseline, hybrid accuracy improves, the local
backhand clip stays a backhand). Eval only: not shipped.
- wing (1b): forehand vs backhand; baseline = the product's side_score rule.
- block (1c): block vs any other non-serve stroke; baseline = the product, which never says block.

    .venv/bin/python -m eval.train_wing train wing      # fit on calibration, freeze to eval/wing_model.json
    .venv/bin/python -m eval.train_wing validate wing   # score the frozen model once
    (the same with `block`; eval/block_model.json)
Calibration windows: eval/work/accuracy-next/{test_7,test_5,test_1}/ (cached by
eval/extract_strokes.py with the hands in eval/labels/openttgames_hands.json)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from technique import pose, strokes

HERE = Path(__file__).resolve().parent
WORK = HERE / "work" / "accuracy-next"
TARGETS = {"wing": lambda r: r["wing"] == "forehand", "block": lambda r: r["subtype"] == "block"}
NAMES = {"wing": ("forehand", "backhand"), "block": ("block", "other")}
CALIBRATION = ["test_7", "test_5", "test_1"]
VALIDATION = ["test_6", "test_3"]   # pre-declared (geometry_protocol.json); never used to fit
FEATURES = ["side_score", "rise", "low_start", "path", "wrist_x", "wrist_vx", "elbow", "turn", "facing",
            "forearm_x", "cross"]
PRECISION_TARGET = 0.9


def _pts(track: pose.PoseTrack) -> np.ndarray:
    return pose._interp_nan(track.lm[:, :, :2]) * [track.width, track.height]


def features(track: pose.PoseTrack, hand: str, c: int) -> dict:
    """Hand-normalised (mirrored for left-handers, so 'bat side' is always +x) body-relative
    features around contact, in torso lengths and degrees."""
    f = dict(strokes.features(track, hand, c))
    p = _pts(track)
    n = len(p)
    c = int(np.clip(c, 0, n - 1))
    bat_sh, free_sh, el, wr = ((pose.R_SHOULDER, pose.L_SHOULDER, pose.R_ELBOW, pose.R_WRIST) if hand != "left"
                               else (pose.L_SHOULDER, pose.R_SHOULDER, pose.L_ELBOW, pose.L_WRIST))
    sh_mid = (p[:, 11] + p[:, 12]) / 2
    hip_mid = (p[:, 23] + p[:, 24]) / 2
    torso = float(np.median(np.linalg.norm(sh_mid - hip_mid, axis=1))) + 1e-6
    axis = p[:, bat_sh] - p[:, free_sh]                    # free shoulder -> bat shoulder
    unit = axis / (np.linalg.norm(axis, axis=1, keepdims=True) + 1e-9)
    rel = (p[:, wr] - sh_mid) / torso
    along = (rel * unit).sum(-1)                           # + = out on the bat-arm side
    fps = track.fps or 30.0
    a, b = max(0, c - int(0.2 * fps)), min(n - 1, c + int(0.2 * fps))
    f["wrist_x"] = float(along[c])
    f["wrist_vx"] = float((along[b] - along[a]) / max(1, b - a) * fps)   # moving toward / away from the bat side
    f["elbow"] = float(pose._angle(p[c, bat_sh], p[c, el], p[c, wr]))
    ang = np.degrees(np.arctan2(axis[:, 1], axis[:, 0]))
    f["turn"] = float(((ang[c] - ang[max(0, c - int(0.3 * fps))]) + 180) % 360 - 180)
    f["facing"] = float(np.linalg.norm(axis[c]) / torso)   # wide = facing the camera, narrow = side-on
    fore = (p[c, wr] - p[c, el]) / torso
    f["forearm_x"] = float((fore * unit[c]).sum())
    f["cross"] = float(np.sign(along[c]) * np.sign(f["wrist_vx"]))
    return {k: (0.0 if not np.isfinite(v) else float(v)) for k, v in f.items() if k in FEATURES}


def load(video: str) -> list[dict]:
    d = WORK / video
    manifest = json.loads((d / "manifest.json").read_text())
    rows = []
    for r in manifest["contacts"]:
        tr = pose.load_track(d / r["track"])
        if tr.valid.mean() < .4:   # the pose visibility floor: no player to classify
            continue
        rows.append({**r, "video": video, "x": features(tr, r["hand"], r["contact_i"]),
                     "baseline": "forehand" if strokes.features(tr, r["hand"], r["contact_i"])["side_score"] > .15
                     else "backhand"})
    return rows


def fit(X: np.ndarray, y: np.ndarray, l2: float = 1.0, steps: int = 3000, lr: float = .1):
    """Logistic regression (gradient descent, L2) on standardised features, both classes
    weighted equally (calibration is 108 backhands to 27 forehands, 39 blocks to 96 others)."""
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = (X - mu) / sd
    pos = max(y.mean(), 1e-6)
    sw = np.where(y > 0, 0.5 / pos, 0.5 / max(1 - pos, 1e-6))
    w, b = np.zeros(Z.shape[1]), 0.0
    for _ in range(steps):
        p = 1 / (1 + np.exp(-(Z @ w + b)))
        g = sw * (p - y)
        w -= lr * (Z.T @ g / len(y) + l2 * w / len(y))
        b -= lr * float(np.mean(g))
    return {"mu": mu.tolist(), "sd": sd.tolist(), "w": w.tolist(), "b": b}


def prob(m: dict, X: np.ndarray) -> np.ndarray:
    Z = (X - np.array(m["mu"])) / np.array(m["sd"])
    return 1 / (1 + np.exp(-(Z @ np.array(m["w"]) + m["b"])))   # P(forehand)


def matrix(rows: list[dict], key: str) -> np.ndarray:
    return np.array([[r["x"][k] for k in FEATURES] for r in rows])


def label(target: str, r: dict) -> str:
    yes, no = NAMES[target]
    return yes if TARGETS[target](r) else no


def baseline(target: str, r: dict) -> str:
    return r["baseline"] if target == "wing" else "other"


def train(target: str) -> None:
    rows = [r for v in CALIBRATION if (WORK / v / "manifest.json").exists() for r in load(v)]
    X, y = matrix(rows, "x"), np.array([TARGETS[target](r) for r in rows], float)
    # The abstain margin from leave-one-video-out on calibration: the smallest |P - 0.5| margin
    # at which held-out decisions reach PRECISION_TARGET.
    held = []
    for v in sorted({r["video"] for r in rows}):
        tr = np.array([r["video"] != v for r in rows])
        m = fit(X[tr], y[tr])
        held += list(zip(prob(m, X[~tr]), y[~tr]))
    margin = 0.45
    for m_ in np.arange(0.0, 0.46, 0.01):
        dec = [(p, t) for p, t in held if abs(p - .5) >= m_]
        if dec and np.mean([(p > .5) == t for p, t in dec]) >= PRECISION_TARGET and len(dec) >= 5:
            margin = float(m_)
            break
    model = {"target": target, "classes": NAMES[target], "features": FEATURES, **fit(X, y), "margin": round(margin, 2),
             "positives": int(y.sum()),
             "calibration": {v: sum(r["video"] == v for r in rows) for v in CALIBRATION},
             "loo": {"n": len(held), "decisions": sum(abs(p - .5) >= margin for p, _ in held),
                     "precision": round(float(np.mean([(p > .5) == t for p, t in held if abs(p - .5) >= margin])), 3)
                     if any(abs(p - .5) >= margin for p, _ in held) else None,
                     "accuracy_all": round(float(np.mean([(p > .5) == t for p, t in held])), 3)}}
    code = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    model["frozen"] = {"script_sha256": code, "validation": VALIDATION,
                       "note": "fitted on calibration only; validation scored once after this freeze"}
    (HERE / f"{target}_model.json").write_text(json.dumps(model, indent=1, default=float))
    print(json.dumps({k: model[k] for k in ("margin", "positives", "calibration", "loo")}, indent=1, default=float))


def decide(model: dict, x: dict) -> str | None:
    p = float(prob(model, np.array([[x[k] for k in model["features"]]]))[0])
    yes, no = model["classes"]
    return None if abs(p - .5) < model["margin"] else (yes if p > .5 else no)


def validate(target: str) -> dict:
    model = json.loads((HERE / f"{target}_model.json").read_text())
    if model["frozen"]["script_sha256"] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        sys.exit("the classifier changed after it was frozen: retrain on calibration before validating")
    protocol = json.loads((HERE / "geometry_protocol.json").read_text())
    out = {}
    for v in VALIDATION:
        rows = load(v)
        for r in rows:
            r["truth"] = label(target, r)
            r["base"] = baseline(target, r)
            r["learned"] = decide(model, r["x"])
            r["hybrid"] = r["learned"] or r["base"]
        dec = [r for r in rows if r["learned"]]
        res = {"n": len(rows), "decisions": len(dec),
               "selective_precision": round(float(np.mean([r["learned"] == r["truth"] for r in dec])), 3) if dec else None,
               "positives": sum(r["truth"] == model["classes"][0] for r in rows)}
        for key in ("base", "hybrid"):
            rec = {w: (round(float(np.mean([r[key] == w for r in rows if r["truth"] == w])), 3)
                       if any(r["truth"] == w for r in rows) else None) for w in model["classes"]}
            res[key] = {"correct": sum(r[key] == r["truth"] for r in rows), "recall": rec}
        out[v] = res
    # The local regression clips: the user's own backhand must stay a backhand.
    local = {}
    for name, wing in ((("local_backhand", "backhand"), ("local_forehand", "forehand")) if target == "wing" else ()):
        clip = WORK / f"{name}.mp4"
        if clip.exists():
            tr = pose.extract_pose(clip)
            side = "right"
            peaks = pose.swing_peaks(tr, side)
            c = int(peaks[np.argmax(pose.wrist_speeds(tr)[1][peaks])]) if len(peaks) else len(tr.times) // 2
            local[name] = {"want": wing, "learned": decide(model, features(tr, side, c))}
    report = {"target": target, "per_video": out, "local": local, "gates": protocol["promotion_criteria"],
              "verdict": verdict(out, local, protocol["promotion_criteria"], model["classes"])}
    print(json.dumps(report, indent=1))
    (HERE / f"{target}_validation.json").write_text(json.dumps(report, indent=1))
    return report


def verdict(out: dict, local: dict, gates: dict, classes) -> dict:
    """The pre-declared gates over both validation videos together."""
    dec = sum(v["decisions"] for v in out.values())
    precise = sum(round(v["selective_precision"] * v["decisions"]) for v in out.values() if v["decisions"])
    precision = precise / dec if dec else None
    drops = {}
    for c in classes:
        b = [v["base"]["recall"][c] for v in out.values() if v["base"]["recall"][c] is not None]
        h = [v["hybrid"]["recall"][c] for v in out.values() if v["hybrid"]["recall"][c] is not None]
        drops[c] = round(float(np.mean(b) - np.mean(h)), 3) if b else None
    better = sum(v["hybrid"]["correct"] for v in out.values()) > sum(v["base"]["correct"] for v in out.values())
    local_ok = all(l["learned"] in (None, l["want"]) for l in local.values()) if local else None
    checks = {"selective_precision": precision is not None and precision >= gates["selective_precision_min"],
              "recall_drop": all(d is None or d <= gates["per_wing_recall_drop_max"] for d in drops.values()),
              "hybrid_improves": better, "local_backhand": local_ok}
    return {"selective_precision": round(precision, 3) if precision is not None else None, "recall_drop": drops,
            "checks": checks, "promote": all(v for v in checks.values() if v is not None)}


if __name__ == "__main__":
    {"train": train, "validate": validate}[sys.argv[1]](sys.argv[2])
