"""One video of the matched pros: a short title card per pro, then their cached breakdown."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from technique.media import encode_frames
from technique.render import ACCENT, BG, GREY, H, W, WHITE, _brand, font

from .match import DATA

CARD_S = 1.6


def _card(rank: int, m: dict, stroke: str) -> np.ndarray:
    img = Image.new("RGB", (W, H), BG[::-1])
    d = ImageDraw.Draw(img)
    _brand(d)
    d.text((60, 640), f"#{rank} MATCH · {stroke.upper()}", font=font("bold", 48), fill=ACCENT)
    name = m["name"].upper()
    f = font("display", 150)
    while d.textlength(name, font=f) > W - 120 and f.size > 70:
        f = font("display", f.size - 8)
    d.text((56, 710), name, font=f, fill=WHITE)
    y = 710 + int(f.size * 1.05)
    facts = f"{m['height_cm']} cm · {m['bat_hand']}-handed · {m.get('country') or ''}".strip(" ·")
    d.text((60, y + 10), facts, font=font("semibold", 46), fill=GREY)
    d.text((60, y + 90), f"{m['score']}%", font=font("display", 120), fill=ACCENT)
    d.text((60 + d.textlength(f"{m['score']}%", font=font("display", 120)) + 24, y + 150),
           "body match", font=font("semibold", 44), fill=WHITE)
    return np.array(img)[:, :, ::-1].copy()


def compile_matches(matches: list[dict], stroke: str, workdir: Path, dest: Path) -> Path | None:
    """Concatenates card + breakdown for each match that has a cached video. None if none do."""
    workdir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    for i, m in enumerate(matches, 1):
        video = DATA / m["breakdown"] if m.get("breakdown") else None
        if not video or not video.exists():
            continue
        card = workdir / f"card{i}.mp4"
        frame = _card(i, m, stroke)
        encode_frames((frame for _ in range(int(CARD_S * 30))), card, W, H, 30)
        parts += [card, video]
    if not parts:
        return None
    listing = workdir / "list.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    # Every part comes from our own encoder (same size, fps and codec), so stream copy is safe.
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", "-movflags", "+faststart", str(dest)], check=True)
    return dest
