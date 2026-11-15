"""Build pro profiles for "Find my pro match".

For every player and stroke (forehand, backhand) this searches YouTube, then for each
candidate: downloads the first two minutes at <=720p, picks an ~8 s window with the most
play, runs the technique pipeline on it (720p clip, MediaPipe pose, cached breakdown
video), computes the body profile and joint-angle curves, and deletes the raw download.
Two good clips per stroke are kept. Clips and videos stay in backend/data/players/
(git-ignored); players.json gets the clip references and profiles.json the numbers.

Usage: cd backend && .venv/bin/python -m players.build [--only ma-long] [--workers 4]"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

os.environ.setdefault("GLOG_minloglevel", "2")

from .match import DATA, PROFILES, ROSTER  # noqa: E402

STROKES = ("forehand", "backhand")
CLIPS_PER_STROKE = 2
SEARCH_RESULTS = 8
SECTION_S = 120
WINDOW_S = 8.0
_YDL = {"quiet": True, "no_warnings": True, "noprogress": True, "js_runtimes": {"node": {}}}


def aliases(name: str) -> list[str]:
    parts = name.lower().split()
    out = [name.lower(), "".join(parts)]
    if len(parts[-1]) > 3:
        out.append(parts[-1])          # family name last: Harimoto, Calderano, Boll, Ito, Hayata
    if len(parts) == 2 and len(parts[1]) > 4:
        out.append(parts[1])           # Chinese given name: Zhendong, Chuqin, Yingsha
    return out


def search(name: str, stroke: str) -> list[dict]:
    import yt_dlp

    names = aliases(name)
    seen, out = set(), []
    for q in (f"{name} {stroke} slow motion", f"{name} {stroke} training"):
        with yt_dlp.YoutubeDL({**_YDL, "extract_flat": True}) as ydl:
            res = ydl.extract_info(f"ytsearch{SEARCH_RESULTS}:{q}", download=False)
        for e in res.get("entries", []):
            title = (e.get("title") or "").lower()
            dur = e.get("duration") or 0
            if e["id"] in seen or not any(a in title for a in names) or not 8 <= dur <= 900:
                continue
            seen.add(e["id"])
            score = (stroke in title) * 2 + ("slow" in title) + ("training" in title) - (" vs " in title)
            out.append({"id": e["id"], "title": e.get("title"), "duration": dur, "score": score})
        time.sleep(8)
    return sorted(out, key=lambda c: -c["score"])


def download_section(video_id: str, dest: Path) -> Path:
    import yt_dlp
    from yt_dlp.utils import download_range_func

    opts = {**_YDL, "format": "bv*+ba/b", "format_sort": ["res:720", "vcodec:h264", "acodec:m4a"],
            "merge_output_format": "mp4", "outtmpl": str(dest / f"{video_id}.%(ext)s"),
            "download_ranges": download_range_func(None, [(0, SECTION_S)]), "force_keyframes_at_cuts": False}
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
    files = sorted(dest.glob(f"{video_id}.*"))
    if not files:
        raise RuntimeError("download produced no file")
    return files[0]


def process_clip(raw: str, out_dir: str, name: str, stroke: str, hand: str) -> dict:
    """Runs in a worker process: window, pipeline (pose + cached breakdown), profile."""
    import numpy as np

    from technique import media, pose
    from technique.pipeline import choose_window, run_video

    from .body import angle_curves, body_ratios

    out = Path(out_dir)
    info = media.probe(raw)
    win = choose_window(raw, info["duration"], WINDOW_S, out, progress=lambda m: None)
    start, end = win["start"], min(win["end"], win["start"] + WINDOW_S)
    res = run_video(raw, out_dir, stroke=stroke, player=name, analyzer="offline",
                    window=(start, end), hand=hand, progress=lambda m: None)
    track = pose.load_track(res["outputs"]["pose_track"])
    summary = json.loads(Path(res["outputs"]["pose_summary_json"]).read_text())
    side = res["bat_hand"]["side"]
    curves = angle_curves(track, side, res["contact_frame"])
    return {"start": round(start, 2), "end": round(end, 2), "visible": summary["person_visible_ratio"],
            "swings": summary["swing_count"], "body": body_ratios(track), "curves": curves,
            "stroke_type": res.get("stroke_type"), "side": side,
            "valid": bool(summary["person_visible_ratio"] >= 0.6 and summary["swing_count"] >= 1
                          and np.isfinite(list(body_ratios(track).values())[:4]).all())}


def build(only: list[str] | None, workers: int) -> None:
    roster = json.loads(ROSTER.read_text())
    profiles = json.loads(PROFILES.read_text()) if PROFILES.exists() else {"players": {}}
    raw_dir = DATA / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(workers) as pool:
        for p in roster["players"]:
            if only and p["id"] not in only:
                continue
            prof = profiles["players"].get(p["id"], {"strokes": {}})
            p.setdefault("clips", {})
            for stroke in STROKES:
                if len(prof["strokes"].get(stroke, [])) >= CLIPS_PER_STROKE:
                    continue  # already built: the script resumes where it stopped
                kept, pending = [], []
                for cand in search(p["name"], stroke):
                    while len(pending) >= 2:  # keep two clips processing while we download
                        _collect(*pending.pop(0), kept)
                    if len(kept) >= CLIPS_PER_STROKE:
                        break
                    try:
                        raw = download_section(cand["id"], raw_dir)
                    except Exception as e:  # unavailable, blocked...: try the next one
                        print(f"  skip {cand['id']}: {str(e)[:120]}", flush=True)
                        if "not a bot" in str(e):
                            raise SystemExit("YouTube is blocking downloads; stopping. Re-run later.")
                        continue
                    outd = DATA / p["id"] / f"{stroke}_{cand['id']}"
                    outd.mkdir(parents=True, exist_ok=True)
                    fut = pool.submit(process_clip, str(raw), str(outd), p["name"], stroke, p["bat_hand"])
                    pending.append((fut, cand, outd))
                    time.sleep(15)  # be polite between downloads
                for item in pending:
                    _collect(*item, kept)
                for extra in kept[CLIPS_PER_STROKE:]:
                    shutil.rmtree(DATA / Path(extra["breakdown"]).parent, ignore_errors=True)
                _store(p, prof, stroke, kept[:CLIPS_PER_STROKE])
                print(f"{p['name']} {stroke}: {len(prof['strokes'].get(stroke, []))} clips", flush=True)
            _save(roster, profiles, p, prof)
    shutil.rmtree(raw_dir, ignore_errors=True)


def _store(p: dict, prof: dict, stroke: str, kept: list[dict]) -> None:
    """Append new clips to the player's roster entry and profile (keeps earlier ones)."""
    have = {c["url"] for c in prof["strokes"].get(stroke, [])}
    for k in kept:
        url = f"https://www.youtube.com/watch?v={k['id']}"
        if url in have or len(prof["strokes"].get(stroke, [])) >= CLIPS_PER_STROKE:
            continue
        p["clips"].setdefault(stroke, []).append({"url": url, "title": k["title"], "start": k["start"], "end": k["end"]})
        prof["strokes"].setdefault(stroke, []).append({"url": url, "breakdown": k["breakdown"], "curves": k["curves"],
                                                       "stroke_type": k["stroke_type"], "body": k["body"]})


def _save(roster: dict, profiles: dict, p: dict, prof: dict) -> None:
    bodies = [c["body"] for s in prof["strokes"].values() for c in s]
    if bodies:
        keys = [k for k in bodies[0] if k not in ("units", "height_units")]
        prof["body"] = {k: round(float(sorted(b[k] for b in bodies)[len(bodies) // 2]), 3) for k in keys}
        profiles["players"][p["id"]] = prof
    ROSTER.write_text(json.dumps(roster, indent=2) + "\n")
    PROFILES.write_text(json.dumps(profiles, indent=2) + "\n")


def add_local(player_id: str, stroke: str, file: str, url: str, title: str) -> None:
    """Add a clip from a video already on disk (e.g. downloaded earlier) instead of searching."""
    roster = json.loads(ROSTER.read_text())
    profiles = json.loads(PROFILES.read_text()) if PROFILES.exists() else {"players": {}}
    p = next(x for x in roster["players"] if x["id"] == player_id)
    prof = profiles["players"].get(player_id, {"strokes": {}})
    vid = url.rsplit("=", 1)[-1].rsplit("/", 1)[-1]
    outd = DATA / player_id / f"{stroke}_{vid}"
    outd.mkdir(parents=True, exist_ok=True)
    r = process_clip(file, str(outd), p["name"], stroke, p["bat_hand"])
    if not r["valid"]:
        raise SystemExit(f"clip rejected: visible={r['visible']} swings={r['swings']}")
    _store(p, prof, stroke, [{**r, "id": vid, "title": title, "breakdown": str((outd / "breakdown.mp4").relative_to(DATA))}])
    _save(roster, profiles, p, prof)
    print(f"added {p['name']} {stroke} from {file}")


def _collect(fut, cand: dict, outd: Path, kept: list) -> None:
    raw = DATA / "raw"
    try:
        r = fut.result()
    except Exception as e:
        print(f"  failed {cand['id']}: {str(e)[:160]}", flush=True)
        r = {"valid": False}
    for f in raw.glob(f"{cand['id']}.*"):
        f.unlink()  # the raw download is never kept
    if not r.get("valid"):
        shutil.rmtree(outd, ignore_errors=True)
        return
    for extra in ("input.mp4",):
        (outd / extra).unlink(missing_ok=True)
    rel = (outd / "breakdown.mp4").relative_to(DATA)
    kept.append({**r, **cand, "breakdown": str(rel)})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--local", nargs=5, metavar=("PLAYER_ID", "STROKE", "FILE", "YOUTUBE_URL", "TITLE"),
                    help="add one clip from a local file instead of searching")
    args = ap.parse_args()
    if args.local:
        add_local(*args.local)
    else:
        build(args.only, args.workers)


if __name__ == "__main__":
    main()
