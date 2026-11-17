"""Runs the rally detector against the labeled videos and prints a metrics table.

    .venv/bin/python -m eval.run            # audio-only detector
    .venv/bin/python -m eval.run --pose     # plus the floor-bounce pose filter (slow)

Labels live in eval/labels/<name>.json; videos in ../samples/ (git-ignored)."""
from __future__ import annotations

import argparse
import json
import hashlib
import importlib
import subprocess
import sys
import types
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app import rally

from .metrics import match_rallies, onset_play_split

LABELS = Path(__file__).parent / "labels"
SAMPLES = Path(__file__).resolve().parent.parent.parent / "samples"


@contextmanager
def baseline_modules(revision: str) -> Iterator[tuple[types.ModuleType, types.ModuleType]]:
    """Load a snapshot package so __file__ and sibling imports belong to that revision."""
    with tempfile.TemporaryDirectory(prefix="ttskill-baseline-") as tmp:
        package_name = "_ttskill_baseline_" + Path(tmp).name.replace("-", "_")
        package = types.ModuleType(package_name)
        package.__path__ = [tmp]
        sys.modules[package_name] = package
        try:
            for name in ("rally", "floor_bounce", "clips"):
                result = subprocess.run(["git", "show", f"{revision}:backend/app/{name}.py"],
                                        capture_output=True, text=True)
                if name == "clips" and result.returncode:  # introduced after Milestone 1
                    continue
                result.check_returncode()
                (Path(tmp) / f"{name}.py").write_text(result.stdout)
            yield (importlib.import_module(f"{package_name}.rally"),
                   importlib.import_module(f"{package_name}.floor_bounce"))
        finally:
            for name in list(sys.modules):
                if name == package_name or name.startswith(package_name + "."):
                    del sys.modules[name]


def load_labels() -> list[dict]:
    out = []
    for p in sorted(LABELS.glob("*.json")):
        gt = json.loads(p.read_text())
        # "also": other encodes of the same footage (same timeline, same labels).
        for i, rel in enumerate([gt["video"], *gt.get("also", [])]):
            video = SAMPLES / Path(rel).name
            name = p.stem if i == 0 else f"{p.stem}@{video.stem}"
            if video.exists():
                out.append({**gt, "name": name, "video": video, "labels": p})
            else:
                print(f"skip {name}: {video} not found")
    return out


def _evaluate(gt: dict, workdir: Path, use_pose: bool,
             threshold: float = 3.0, gap: float = 1.6, min_hits: int = 4,
             detector=rally, filter_module=None) -> dict:
    wav = detector.extract_audio(gt["video"], workdir / f"{gt['name']}.wav")
    onsets = detector.detect_hits(wav, threshold)
    found = detector.detect_rallies(gt["video"], workdir, threshold, gap, min_hits)
    visual = None
    if use_pose:
        from app import floor_bounce
        module = filter_module or floor_bounce
        if hasattr(module, "refine"):
            result = module.refine(gt["video"], found, min_hits=min_hits)
            found = result.kept
            visual = {"joins": result.joins,
                      "dropped": [{**r.to_dict(), "reason": r.note} for r in result.dropped]}
        else:
            found, dropped = module.drop_floor_bounces(gt["video"], found)
            visual = {"joins": [], "dropped": [r.to_dict() for r in dropped]}
    truth = [(r["start"], r["end"]) for r in gt["rallies"]]
    prep = [tuple(s) for s in gt.get("prep", [])]
    return {
        "label_sha256": hashlib.sha256(gt["labels"].read_bytes()).hexdigest(),
        "video_sha256": hashlib.sha256(gt["video"].read_bytes()).hexdigest(),
        "contact_metrics": None,  # span labels cannot establish contact-level precision/recall
        "visual": visual,
        "rallies": match_rallies([(r.start, r.end) for r in found], truth),
        "onsets_play_window_proxy": onset_play_split(list(onsets), truth, prep),
        "found": [r.to_dict() for r in found],
    }


def evaluate(gt: dict, workdir: Path, use_pose: bool, revision: str | None = None, **kwargs) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    # Production writes audio.wav: concurrent evaluations must never share that path.
    with tempfile.TemporaryDirectory(dir=workdir, prefix=gt["name"] + "-") as tmp:
        if revision:
            with baseline_modules(revision) as (detector, filter_module):
                return _evaluate(gt, Path(tmp), use_pose, detector=detector,
                                 filter_module=filter_module, **kwargs)
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
