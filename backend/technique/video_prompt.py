"""Stage 2: turn a StrokeBreakdown into a text-to-video prompt.

No paid video API is wired up yet (Duke's call, 2026-11-14). The pipeline writes these
prompts to disk so any provider (Nova Reel, Veo, Runway, Luma...) can be plugged in
later via `generate_video()`; until then the pose-overlay render is the video output."""
from __future__ import annotations

from .schema import StrokeBreakdown
from .strokes import STROKE_TYPES

import i18n

STYLE = (
    "stylized grey wireframe 3D athlete on a dark studio background, blue table tennis table, "
    "cinematic side-on camera, slow motion, glowing cyan trail on the bat, high detail"
)
NEGATIVE = "text, captions, logos, watermark, extra limbs, distorted hands, crowd, blurry"


def _clip(s: str, n: int) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "."


# The prompt's own words per language. The negative prompt stays English: it is a keyword list
# for the video model, never shown to the user.
_FRAME = {
    "en": dict(hand="{hand}-handed ", player="a {hand}table tennis player", named="{name}, a {hand}table tennis player",
               main="{who} performs a {stroke}. Grip: {grip} Stance: {stance} Swing: {swing} Contact: {contact} "
                    "Finish: {finish} Style: {style}.",
               shot="{who}, {stroke}, moment: {title} - {lines} {style}.", style=STYLE),
    "vi": dict(hand="tay {hand} ", player="một người chơi bóng bàn {hand}", named="{name}, người chơi bóng bàn {hand}",
               main="{who} thực hiện cú {stroke}. Cầm vợt: {grip} Tư thế: {stance} Vung vợt: {swing} "
                    "Tiếp xúc: {contact} Kết thúc: {finish} Phong cách: {style}.",
               shot="{who}, {stroke}, khoảnh khắc: {title} - {lines} {style}.",
               style="vận động viên 3D khung lưới màu xám trên nền studio tối, bàn bóng bàn xanh dương, góc quay "
                     "ngang điện ảnh, quay chậm, vệt sáng xanh cyan trên vợt, chi tiết cao"),
}


def build_prompts(b: StrokeBreakdown, max_chars: int = 512, lang: str = "en") -> dict:
    """lang: the prompt's language, the same as the breakdown's text (a job's `lang`)."""
    lang = i18n.norm(lang)
    w = _FRAME[lang]
    side = {"left": "trái", "right": "phải"}.get(b.handedness, "") if lang == "vi" else b.handedness
    hand = w["hand"].format(hand=side) if b.handedness in ("left", "right") else ""
    who = (w["player"] if b.player in ("", "Player") else w["named"]).format(hand=hand, name=b.player).replace("  ", " ").strip()
    st = STROKE_TYPES.get(b.stroke_type or "")
    stroke = (i18n.stroke_label(st.key, lang) if lang != "en" else st.label.lower()) if st else (
        i18n.stroke_label(b.stroke, lang) if lang != "en" else b.stroke)
    main = w["main"].format(who=who, stroke=stroke, grip=b.grip, stance=b.stance, swing=b.swing_path,
                            contact=b.contact_point, finish=b.follow_through, style=w["style"])
    shots = []
    for i, s in enumerate(b.steps, 1):
        shots.append({
            "step": i,
            "title": s.title,
            "prompt": _clip(w["shot"].format(who=who, stroke=stroke, title=s.title.lower(), lines=" ".join(s.lines),
                                             style=w["style"]), max_chars),
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
