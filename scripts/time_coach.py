"""Time one Coach job, stage by stage: every Claude call (seconds, tokens, dollars), pose,
matching, rendering. Runs the real pipeline in-process on a local video.

    backend/.venv/bin/python scripts/time_coach.py samples/coaching-demo.mp4
    backend/.venv/bin/python scripts/time_coach.py samples/IMG_8782.MOV --engine fallback

--engine agent loads ANTHROPIC_API_KEY from backend/.env into this process only (nothing
else loads that file) and bills real API calls. The job record and a JSON copy of the timings
go to backend/eval/coach_speed/<label>-<video>.json."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

REQUEST = "Here's my match, show my best rallies and fix my forehand"   # the demo's request


def load_key() -> None:
    env = ROOT / "backend" / ".env"
    if os.environ.get("ANTHROPIC_API_KEY") or not env.exists():
        return
    for line in env.read_text().splitlines():
        if line.startswith("ANTHROPIC_API_KEY=") and line.split("=", 1)[1].strip():
            os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip().strip('"')


CATEGORIES = [   # first match wins, on the leaf stage name
    ("Claude", lambda r: r["kind"] == "llm"),
    ("pose", lambda r: "pose (" in r["leaf"] or r["leaf"].startswith("seed") or r["leaf"] == "choose_window"),
    ("render", lambda r: r["leaf"].startswith("render") or "compile" in r["leaf"] or "cut + join" in r["leaf"]),
    ("matching", lambda r: r["leaf"].startswith("match") or "height" in r["leaf"]),
    ("audio/rallies", lambda r: "rallies" in r["leaf"] or "non-play" in r["leaf"]),
]


def table(t: dict) -> str:
    rows = sorted(t["rows"], key=lambda r: (r["start_s"], r["depth"]))
    out = [f"{'stage':64s} {'start':>7s} {'secs':>7s}  {'tokens in/out/cache w/r':>26s} {'$':>7s}"]
    for r in rows:
        name = "  " * r["depth"] + r["stage"].split(" / ")[-1]
        if r["kind"] == "llm":
            tok = f"{r['input']}/{r['output']}/{r['cache_write']}/{r['cache_read']}"
            dollars = f"{r['cost']:.4f}" if r.get("cost") is not None else "?"
            out.append(f"{name[:64]:64s} {r['start_s']:7.1f} {r['seconds']:7.1f}  {tok:>26s} {dollars:>7s}  {r['model']}")
        else:
            out.append(f"{name[:64]:64s} {r['start_s']:7.1f} {r['seconds']:7.1f}")
    # Leaf time per category (stages that contain other stages aren't double counted).
    leaves = []
    for r in rows:
        inner = [o for o in rows if o is not r and o["stage"].startswith(r["stage"] + " / ")]
        if r["kind"] == "llm" or not inner:
            leaves.append({**r, "leaf": r["stage"].split(" / ")[-1]})
    totals: dict[str, float] = {}
    for r in leaves:
        cat = next((c for c, test in CATEGORIES if test(r)), "other")
        totals[cat] = totals.get(cat, 0.0) + r["seconds"]
    out.append("")
    out.append(f"wall {t['wall_s']} s; Claude calls {t['llm_calls']} ({t['llm_s']} s); tokens {t['tokens']}; cost ${t['cost_usd']}")
    out.append("leaf seconds by kind (overlapping work counts each time): "
               + ", ".join(f"{k} {v:.1f}" for k, v in sorted(totals.items(), key=lambda kv: -kv[1])))
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--engine", choices=["agent", "fallback"], default="agent")
    ap.add_argument("--request", default=REQUEST)
    ap.add_argument("--label", default="phase0")
    args = ap.parse_args()
    if args.engine == "agent":
        load_key()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("No ANTHROPIC_API_KEY (environment or backend/.env)")
    else:
        os.environ.pop("ANTHROPIC_API_KEY", None)

    from agent.coach import run_coach
    from app import jobs

    video = Path(args.video).resolve()
    job = jobs.create("coach", {"request": args.request, "video": video.name, "url": None, "timing_run": args.label})
    path = jobs.job_dir(job["id"]) / f"input{video.suffix.lower()}"
    shutil.copyfile(video, path)
    jobs.run(run_coach, job["id"], path, None, args.request)
    done = jobs.load(job["id"])
    print(f"job {job['id']}: {done['status']} ({done.get('engine')}) - {done.get('message')}")
    print(table(done["timings"]))
    dest = ROOT / "backend" / "eval" / "coach_speed"
    dest.mkdir(parents=True, exist_ok=True)
    keep = {k: done.get(k) for k in ("id", "status", "engine", "engineNote", "summary", "outputs", "breakdown",
                                     "matches", "timings", "todos")}
    (dest / f"{args.label}-{args.engine}-{video.stem}.json").write_text(json.dumps(keep, indent=2, default=str))


if __name__ == "__main__":
    main()
