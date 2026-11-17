"""Runs the rally detector against the labeled videos and prints a metrics table.

    .venv/bin/python -m eval.run            # audio-only detector
    .venv/bin/python -m eval.run --pose     # plus the floor-bounce pose filter (slow)

Labels live in eval/labels/<name>.json; videos in ../samples/ (git-ignored)."""
from __future__ import annotations

import argparse
import json
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


def evaluate(gt: dict, workdir: Path, use_pose: bool,
             threshold: float = 3.0, gap: float = 1.6, min_hits: int = 4) -> dict:
    wav = rally.extract_audio(gt["video"], workdir / f"{gt['name']}.wav")
    onsets = rally.detect_hits(wav, threshold)
    found = rally.group_rallies(onsets, gap, min_hits)
    if use_pose:
        from app.floor_bounce import drop_floor_bounces
        found, _ = drop_floor_bounces(gt["video"], found)
    truth = [(r["start"], r["end"]) for r in gt["rallies"]]
    prep = [tuple(s) for s in gt.get("prep", [])]
    return {
        "rallies": match_rallies([(r.start, r.end) for r in found], truth),
        "onsets": onset_play_split(list(onsets), truth, prep),
        "found": [r.to_dict() for r in found],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pose", action="store_true", help="also run the floor-bounce pose filter")
    ap.add_argument("--threshold", type=float, default=3.0)
    args = ap.parse_args()
    workdir = Path(__file__).parent / "work"
    workdir.mkdir(exist_ok=True)
    rows = []
    for gt in load_labels():
        res = evaluate(gt, workdir, args.pose, threshold=args.threshold)
        rows.append((gt["name"], res))
        print(f"\n== {gt['name']}")
        print(json.dumps({k: v for k, v in res.items() if k != "found"}, indent=2))
    print("\n| video | rally P | rally R | F1 | merges | splits | false rallies | onset play-precision |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for name, res in rows:
        r, o = res["rallies"], res["onsets"]
        print(f"| {name} | {r['precision']} | {r['recall']} | {r['f1']} | {r['merges']} "
              f"| {r['splits']} | {r['false_rallies']} | {o['play_precision']} |")


if __name__ == "__main__":
    main()
