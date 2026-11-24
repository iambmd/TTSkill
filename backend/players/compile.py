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


def _card(rank: int, m: dict, stroke: str, has_clip: bool = True, lang: str = "en") -> np.ndarray:
    import i18n

    lang = i18n.norm(lang)
    w = i18n.MATCH[lang]
    stroke_name = i18n.stroke_label(stroke, lang).lower() if lang != "en" else stroke
    img = Image.new("RGB", (W, H), BG[::-1])
    d = ImageDraw.Draw(img)
    _brand(d)
    d.text((60, 640), w["card_rank"].format(rank=rank, stroke=stroke_name.upper()), font=font("bold", 48), fill=ACCENT)
    name = m["name"].upper()
    f = font("display", 150)
    while d.textlength(name, font=f) > W - 120 and f.size > 70:
        f = font("display", f.size - 8)
    d.text((56, 710), name, font=f, fill=WHITE)
    y = 710 + int(f.size * 1.05)
    hand = i18n.HANDS_VI.get(m["bat_hand"], m["bat_hand"]) if lang == "vi" else m["bat_hand"]
    grip = m.get("grip") or "shakehand"
    facts = (f"{m['height_cm']} cm · {w['card_hand'].format(hand=hand)} · {w['grips'].get(grip, grip)} · "
             f"{m.get('country') or ''}")
    facts = facts.strip(" ·")
    d.text((60, y + 10), facts, font=font("semibold", 46), fill=GREY)
    d.text((60, y + 90), f"{m['score']}%", font=font("display", 120), fill=ACCENT)
    d.text((60 + d.textlength(f"{m['score']}%", font=font("display", 120)) + 24, y + 150),
           w["card_body"], font=font("semibold", 44), fill=WHITE)
    if not has_clip:
        d.text((60, y + 290), w["card_no_clip"].format(stroke=stroke_name, name=m["name"].split()[-1]),
               font=font("semibold", 46), fill=GREY)
    return np.array(img)[:, :, ::-1].copy()


def compile_matches(matches: list[dict], stroke: str, workdir: Path, dest: Path, lang: str = "en") -> Path | None:
    """A card per match in rank order, each followed by the pro's cached breakdown when there
    is one. A pro can rank first on body proportions with no usable clip of this stroke
    (Ovtcharov's forehands tracked his sparring partner and were dropped); skipping him made
    the video open on "#2 MATCH" under a list that starts with him. None if no pro has a clip."""
    workdir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    clips = 0
    for i, m in enumerate(matches, 1):
        video = DATA / m["breakdown"] if m.get("breakdown") else None
        has_clip = bool(video and video.exists())
        card = workdir / f"card{i}.mp4"
        frame = _card(i, m, stroke, has_clip, lang)
        # Hold a card with no clip after it a little longer, so the note can be read.
        encode_frames((frame for _ in range(int(CARD_S * (1 if has_clip else 1.5) * 30))), card, W, H, 30)
        parts += [card, video] if has_clip else [card]
        clips += has_clip
    if not clips:
        return None
    listing = workdir / "list.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    # Every part comes from our own encoder (same size, fps and codec), so stream copy is safe.
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", "-movflags", "+faststart", str(dest)], check=True)
    return dest
