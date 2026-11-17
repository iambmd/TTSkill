"""Experimental play-window classifier; these proxy labels do not identify contact types."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from app import rally

from .metrics import in_spans
from .run import load_labels

WORK = Path(__file__).parent / "work"


def dataset(gt: dict) -> tuple[np.ndarray, np.ndarray]:
    WORK.mkdir(exist_ok=True)
    wav = rally.extract_audio(gt["video"], WORK / f"{gt['name']}.wav")
    from scipy.io import wavfile
    sr, x = wavfile.read(wav)
    x = x.astype(np.float32) / 32768
    onsets = rally.detect_hits(wav, threshold=2.0)
    play = [(r["start"], r["end"]) for r in gt["rallies"]]
    feats = np.stack([rally.onset_features(x, sr, t) for t in onsets])
    in_play = np.array([in_spans(t, play, margin=0.3) for t in onsets])
    # Proxy experiment only: window membership is not a paddle-contact label. Soft in-play onsets (mostly table
    # bounces) sound like pre-serve bounces, so they are excluded instead of forced into
    # the positive class; grouping attaches them to pop-anchored rallies later.
    strong = feats[:, 0] >= 3.0
    keep = ~in_play | strong
    labels = in_play[keep].astype(np.float32)
    return feats[keep], labels


def fit(X: np.ndarray, y: np.ndarray, epochs: int = 3000, lr: float = 0.05) -> dict:
    mean, std = X.mean(0), X.std(0) + 1e-6
    z = (X - mean) / std
    w = np.zeros(X.shape[1], np.float32)
    b = 0.0
    # balance classes so the rarer non-play onsets matter as much
    pos = y.mean()
    sample_w = np.where(y == 1, 0.5 / max(pos, 1e-6), 0.5 / max(1 - pos, 1e-6))
    for _ in range(epochs):
        p = 1 / (1 + np.exp(-(z @ w + b)))
        g = (p - y) * sample_w
        w -= lr * (z.T @ g / len(y) + 1e-3 * w)
        b -= lr * float(g.mean())
    return {"w": w, "b": float(b), "mean": mean, "std": std}


def score(model: dict, X: np.ndarray, y: np.ndarray, thr: float = 0.5) -> str:
    z = (X - model["mean"]) / model["std"]
    p = 1 / (1 + np.exp(-(z @ model["w"] + model["b"]))) >= thr
    tp = int((p & (y == 1)).sum())
    prec = tp / max(int(p.sum()), 1)
    rec = tp / max(int((y == 1).sum()), 1)
    kept_nonplay = int((p & (y == 0)).sum())
    return f"precision {prec:.3f} recall {rec:.3f} (kept {kept_nonplay}/{int((y == 0).sum())} non-play)"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train", nargs="+", required=True)
    ap.add_argument("--validate", nargs="+", required=True)
    ap.add_argument("--output", type=Path, default=WORK / "onset_model.json")
    args = ap.parse_args()
    if set(args.train) & set(args.validate):
        ap.error("training and validation clips must be disjoint")
    labels = {gt["name"]: gt for gt in load_labels()}
    if set(args.train + args.validate) - labels.keys():
        ap.error("a named clip or its labels are missing")
    sets = {n: dataset(labels[n]) for n in args.train + args.validate}
    X = np.concatenate([sets[n][0] for n in args.train])
    y = np.concatenate([sets[n][1] for n in args.train])
    m = fit(X, y)
    for name in args.validate:
        print(f"{name} play-window proxy validation (NOT held-out tuning): {score(m, *sets[name])}")
    out = {"features": rally.FEATURE_NAMES, "w": m["w"].tolist(), "b": m["b"],
           "mean": m["mean"].tolist(), "std": m["std"].tolist(),
           "target": "strong onset in play window; NOT paddle contact",
           "train": args.train, "validation": args.validate,
           "label_sha256": {n: hashlib.sha256((Path(__file__).parent / "labels" / f"{n}.json").read_bytes()).hexdigest()
                            for n in sets}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2))
    print(f"wrote experimental model {args.output}; production does not consume it")


if __name__ == "__main__":
    main()
