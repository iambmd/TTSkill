"""Runs the rally detector against the labeled videos and prints a metrics table.

    .venv/bin/python -m eval.run            # audio-only detector
    .venv/bin/python -m eval.run --pose     # plus the floor-bounce pose filter (slow)

Labels live in eval/labels/<name>.json; videos in ../samples/ (git-ignored)."""
from __future__ import annotations

import argparse
import json
import hashlib
import subprocess
import sys
import types
import tempfile
from pathlib import Path

from app import rally

from .metrics import match_rallies, onset_play_split

LABELS = Path(__file__).parent / "labels"
SAMPLES = Path(__file__).resolve().parent.parent.parent / "samples"


def load_labels() -> list[dict]:
    out = []
    for p in sorted(LABELS.glob("*.json")):
        gt = json.loads(p.read_text())
        video = SAMPLES / Path(gt["video"]).name
        if video.exists():
            out.append({**gt, "name": p.stem, "video": video})
        else:
            print(f"skip {p.stem}: {video} not found")
    return out


def _evaluate(gt: dict, workdir: Path, use_pose: bool,
             threshold: float = 3.0, gap: float = 1.6, min_hits: int = 4,
             revision: str | None = None) -> dict:
    detector = rally
    filter_module = None
    if revision:
        # Load the actual committed code, while keeping the current label revision.
        for name in ("rally", "floor_bounce"):
            source = subprocess.run(["git", "show", f"{revision}:backend/app/{name}.py"],
                                    check=True, capture_output=True, text=True).stdout
            module = types.ModuleType(f"app._eval_{name}")
            sys.modules[module.__name__] = module
            exec(compile(source, f"{revision}/{name}.py", "exec"), module.__dict__)
            if name == "rally":
                detector = module
            else:
                filter_module = module
    wav = detector.extract_audio(gt["video"], workdir / f"{gt['name']}.wav")
    onsets = detector.detect_hits(wav, threshold)
    found = detector.detect_rallies(gt["video"], workdir, threshold, gap, min_hits)
    if use_pose:
        from app.floor_bounce import drop_floor_bounces
        filter_fn = filter_module.drop_floor_bounces if filter_module else drop_floor_bounces
        found, _ = filter_fn(gt["video"], found)
    truth = [(r["start"], r["end"]) for r in gt["rallies"]]
    prep = [tuple(s) for s in gt.get("prep", [])]
    return {
        "label_sha256": hashlib.sha256((LABELS / f"{gt['name']}.json").read_bytes()).hexdigest(),
        "video_sha256": hashlib.sha256(gt["video"].read_bytes()).hexdigest(),
        "contact_metrics": None,  # span labels cannot establish contact-level precision/recall
        "rallies": match_rallies([(r.start, r.end) for r in found], truth),
        "onsets_play_window_proxy": onset_play_split(list(onsets), truth, prep),
        "found": [r.to_dict() for r in found],
    }


def evaluate(gt: dict, workdir: Path, use_pose: bool, **kwargs) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    # Production writes audio.wav: concurrent evaluations must never share that path.
    with tempfile.TemporaryDirectory(dir=workdir, prefix=gt["name"] + "-") as tmp:
        return _evaluate(gt, Path(tmp), use_pose, **kwargs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pose", action="store_true", help="also run the floor-bounce pose filter")
    ap.add_argument("--threshold", type=float, default=3.0)
    ap.add_argument("--baseline", help="Git revision of detector/filter; uses CURRENT labels")
    ap.add_argument("--output", type=Path, help="write full JSON report outside Git")
    args = ap.parse_args()
    workdir = Path(__file__).parent / "work"
    workdir.mkdir(exist_ok=True)
    rows = []
    for gt in load_labels():
        res = evaluate(gt, workdir, args.pose, threshold=args.threshold, revision=args.baseline)
        rows.append((gt["name"], res))
        print(f"\n== {gt['name']}", flush=True)
        if args.output:
            args.output.write_text(json.dumps(dict(rows), indent=2))
        print(json.dumps({k: v for k, v in res.items() if k != "found"}, indent=2))
    print("\n| video | rally P | rally R | F1 | merges | splits | false rallies | onset play-window proxy P |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for name, res in rows:
        r, o = res["rallies"], res["onsets_play_window_proxy"]
        print(f"| {name} | {r['precision']} | {r['recall']} | {r['f1']} | {r['merges']} "
              f"| {r['splits']} | {r['false_rallies']} | {o['play_precision']} |")

    if args.output:
        args.output.write_text(json.dumps(dict(rows), indent=2))


if __name__ == "__main__":
    main()
