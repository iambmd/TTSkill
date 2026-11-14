"""CLI: python -m technique --video clip.mp4 --stroke backhand --out data/jobs/demo
       python -m technique --text "Ma Long keeps his elbow..." --stroke forehand --out ..."""
from __future__ import annotations

import argparse
import json
import os

os.environ.setdefault("GLOG_minloglevel", "2")


def main():
    ap = argparse.ArgumentParser(prog="technique")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--video")
    src.add_argument("--text")
    ap.add_argument("--stroke", default="forehand",
                    choices=["forehand", "backhand", "serve", "flick", "block", "footwork"])
    ap.add_argument("--player")
    ap.add_argument("--out", required=True)
    ap.add_argument("--analyzer", default="auto", choices=["auto", "claude", "offline"])
    ap.add_argument("--start", type=float, help="window start (s); default: auto")
    ap.add_argument("--end", type=float, help="window end (s)")
    ap.add_argument("--window", type=float, default=8.0, help="auto window length (s)")
    args = ap.parse_args()

    from .pipeline import run_text, run_video

    if args.video:
        win = (args.start, args.end) if args.start is not None and args.end is not None else None
        res = run_video(args.video, args.out, args.stroke, args.player, args.analyzer,
                        window=win, window_s=args.window)
    else:
        res = run_text(args.text, args.out, args.stroke, args.player, args.analyzer)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
