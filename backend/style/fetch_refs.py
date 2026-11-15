"""Download style references from a coaching channel into data/style_ref/ (git-ignored).

Reference only: these files are analysed by analyze_refs.py and never committed, served or
shown in the app. Usage: cd backend && .venv/bin/python -m style.fetch_refs"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CHANNEL = "https://www.youtube.com/@swift_TT"
OUT = Path(__file__).resolve().parents[1] / "data" / "style_ref"
N_LONG, N_SHORTS = 4, 10


def latest(tab: str, n: int) -> list[dict]:
    import yt_dlp

    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "playlistend": n,
            "js_runtimes": {"node": {}}}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"{CHANNEL}/{tab}", download=False)
    return [{"id": e["id"], "title": e.get("title"), "duration": e.get("duration"), "kind": tab}
            for e in info.get("entries", [])][:n]


def fetch(entries: list[dict]) -> None:
    import yt_dlp

    opts = {
        "quiet": True, "no_warnings": True, "js_runtimes": {"node": {}},
        "format": "bv*+ba/b", "format_sort": ["res:480", "vcodec:h264", "acodec:m4a"],
        "merge_output_format": "mp4",
        "writeautomaticsub": True, "writesubtitles": True, "subtitleslangs": ["en"],
        "subtitlesformat": "vtt",
        "outtmpl": str(OUT / "%(id)s.%(ext)s"),
        # Be polite: space the requests out.
        "sleep_interval": 4, "max_sleep_interval": 8, "sleep_interval_subtitles": 2,
        "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={e['id']}" for e in entries
                      if not (OUT / f"{e['id']}.mp4").exists()])


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    entries = latest("videos", N_LONG) + latest("shorts", N_SHORTS)
    (OUT / "index.json").write_text(json.dumps(entries, indent=2))
    fetch(entries)
    missing = [e["id"] for e in entries if not (OUT / f"{e['id']}.mp4").exists()]
    print(f"{len(entries) - len(missing)}/{len(entries)} downloaded" + (f"; missing {missing}" if missing else ""))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
