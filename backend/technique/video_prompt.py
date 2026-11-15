"""Stage 2: turn a StrokeBreakdown into a text-to-video prompt.

No paid video API is wired up yet (Duke's call, 2026-11-14). The pipeline writes these
prompts to disk so any provider (Nova Reel, Veo, Runway, Luma...) can be plugged in
later via `generate_video()`; until then the pose-overlay render is the video output."""
from __future__ import annotations

from .schema import StrokeBreakdown
from .strokes import STROKE_TYPES

STYLE = (
    "stylized grey wireframe 3D athlete on a dark studio background, blue table tennis table, "
    "cinematic side-on camera, slow motion, glowing cyan trail on the bat, high detail"
)
NEGATIVE = "text, captions, logos, watermark, extra limbs, distorted hands, crowd, blurry"


def _clip(s: str, n: int) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "."


def build_prompts(b: StrokeBreakdown, max_chars: int = 512) -> dict:
    hand = f"{b.handedness}-handed " if b.handedness in ("left", "right") else ""
    who = f"a {hand}table tennis player" if b.player in ("", "Player") else f"{b.player}, a {hand}table tennis player"
    st = STROKE_TYPES.get(b.stroke_type or "")
    stroke = st.label.lower() if st else b.stroke
    main = (
        f"{who} performs a {stroke}. Grip: {b.grip} Stance: {b.stance} "
        f"Swing: {b.swing_path} Contact: {b.contact_point} Finish: {b.follow_through} "
        f"Style: {STYLE}."
    )
    shots = []
    for i, s in enumerate(b.steps, 1):
        shots.append({
            "step": i,
            "title": s.title,
            "prompt": _clip(
                f"{who}, {stroke}, moment: {s.title.lower()} - {' '.join(s.lines)} {STYLE}.",
                max_chars,
            ),
            "duration_s": 3,
        })
    return {
        "prompt": _clip(main, max_chars),
        "prompt_long": " ".join(main.split()),
        "negative_prompt": NEGATIVE,
        "shots": shots,
        "aspect_ratio": "9:16",
    }


def generate_video(prompts: dict, out_path: str, provider: str = "none") -> str | None:
    """Hook for a text-to-video provider. Only 'none' exists for now (returns None)."""
    if provider in ("", "none", None):
        return None
    raise NotImplementedError(
        f"text-to-video provider '{provider}' is not enabled; ask before adding a paid API"
    )
