"""The one Claude call of a Coach job: what the pipeline measured goes in, the coaching comes
out as structured data (the page's summary, and the breakdown's headline, 3 cards, recap and
drill). Replaces the deep agent's 19 calls (Phase 0: 105 s of model time, $0.36 a job).

The system prompt is static (instructions, the house style, every stroke's coaching focus,
the pro roster's reference numbers) and cached; the job's facts and three frames of the
coached stroke follow it."""
from __future__ import annotations

import base64
import json
import os
import time
from functools import lru_cache
from typing import Literal, Optional

import numpy as np
from pydantic import BaseModel, Field

import i18n
import timing

MODEL = os.environ.get("COACH_MODEL", "claude-sonnet-5-5")
# Measured on coaching-demo (2026-11-18): medium 8.7 s / 1.1k output tokens / $0.017 against the
# default (high) 19-22 s / 2.3-2.8k / $0.034-0.038, with the same fixes and numbers. Blank = default.
EFFORT = os.environ.get("COACH_EFFORT", "medium")


class Card(BaseModel):
    moment: Literal["preparation", "contact", "finish"] = Field(description="Which key moment the card shows")
    title: str = Field(description="Two-word cue in caps, e.g. 'SIT LOWER'")
    lines: list[str] = Field(description="Exactly two short lines (<=45 characters each): what to look for, then why it works")
    callouts: list[str] = Field(default_factory=list, description="0-2 tiny ALL-CAPS labels with the measured number, e.g. 'KNEE 158°'")


class CoachReport(BaseModel):
    summary: str = Field(description=(
        "The answer shown to the user, in Markdown: one opening sentence with the main problem, then "
        "short bold-labelled sections for what was made (best rallies, pro matches) and 'What to work on "
        "first' as 2-3 numbered fixes with the measured numbers and the closest pros' numbers, one thing to "
        "keep, and one drill. Second person, plain words, no file names or links."))
    headline: str = Field(description="3-6 word hook for the breakdown video")
    stroke_type: Optional[str] = Field(default=None, description="The stroke type key given in the facts, or a correction if the frames clearly show another")
    grip: str = Field(description="One line on the grip for this stroke")
    stance: str = Field(description="One line on feet, knee bend and body angle")
    swing_path: str = Field(description="One line on the backswing to forward swing path")
    contact_point: str = Field(description="One line on where the bat meets the ball")
    follow_through: str = Field(description="One line on the finish and recovery")
    cards: list[Card] = Field(description="Exactly 3 cards in time order: preparation, contact, finish")
    recap: str = Field(description="One line joining the three cues")
    drill: str = Field(description="One simple drill the player can do alone")


INSTRUCTIONS = """You are TT Coach, a table tennis coach. The app has already analysed one user's video:
it found the rallies from the sound of ball contact, cut a highlight reel, tracked the user with pose
estimation, measured their stroke at contact, and matched them with the closest professional players
(same bat hand, build, and DTW on joint-angle curves). You get those measurements as JSON, plus three
frames of the stroke being coached (preparation, contact, finish), and you write the coaching.

Rules:
- Coach what the user asked for. If they asked for rallies too, say what the reel holds.
- Every fix comes from a measurement or a pro difference in the facts; quote the numbers (angles in
  degrees, stance in shoulder widths) and the pro you compare with. Never invent numbers.
- Compare a stroke only with the pros' numbers for the same stroke (forehand with forehand).
- When closest_pros is given, name all three with their match % where you say what was made.
- Angle targets are estimates from the pros' numbers; say "about".
- The frames show the user's body; use them to confirm or correct what the numbers suggest (for
  example the stroke type), not to invent new measurements.
- Only if bat_hand_how starts with "assumed", say the bat hand was assumed and that they can tell you
  otherwise; when it was read from the video, don't call it assumed.
- The cards follow the house style below. Their callouts carry the measured numbers.
- The videos are already on the user's screen; don't paste paths or links."""


def _stroke_table() -> str:
    from technique.strokes import STROKE_TYPES

    return "\n".join(f"- {k} ({st.label}): focus on {st.focus}; phases {', '.join(st.phases)}"
                     for k, st in STROKE_TYPES.items())


@lru_cache(None)
def _pro_table() -> str:
    """One line per pro: hand, grip, height, notes, and their median forehand/backhand angles at
    contact (from the cached curves) - the references the user is compared with."""
    from players.match import load_pros

    lines = []
    for p in load_pros():
        bits = [f"{p['name']} ({p.get('country', '?')}): {p.get('bat_hand')}-handed {p.get('grip', 'shakehand')}",
                f"{p.get('height_cm')} cm"]
        if p.get("equipment_notes"):
            bits.append(str(p["equipment_notes"]))
        for stroke, clips in sorted((p.get("strokes") or {}).items()):
            curves = [c["curves"] for c in clips if c.get("curves")]
            if not curves:
                continue
            # The curves are centred on contact: the middle samples, then the median over clips.
            angles = sorted({k for c in curves for k, v in c.items() if isinstance(v, list) and v})
            at = {k: round(float(np.median([np.median(c[k][len(c[k]) // 2 - 1:len(c[k]) // 2 + 2])
                                            for c in curves if isinstance(c.get(k), list) and c[k]])))
                  for k in angles}
            bits.append(f"{stroke} at contact " + ", ".join(f"{k} {v}°" for k, v in at.items()))
        lines.append("- " + "; ".join(bits))
    return "\n".join(lines)


def system_blocks() -> list[dict]:
    """The static prompt. Byte-identical across jobs, so the cache can serve it."""
    from technique import style

    text = (f"{INSTRUCTIONS}\n\n{style.prompt_guide()}\n\nStroke types and what matters for each:\n"
            f"{_stroke_table()}\n\nThe professional players in the app (reference numbers):\n{_pro_table()}")
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def _jpeg(frame: np.ndarray, width: int = 640) -> str:
    import cv2

    h, w = frame.shape[:2]
    if w > width:
        frame = cv2.resize(frame, (width, round(h * width / w)))
    return base64.standard_b64encode(cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()).decode()


def write(request: str, facts: dict, frames: list[tuple[str, np.ndarray]], client=None,
          lang: str = "en") -> tuple[CoachReport, str]:
    """The coaching for one job. frames: (label, BGR image) of the coached stroke.
    lang: the language to write in; its rule follows the cached system prompt, in the user turn.
    Returns the report and the model that wrote it."""
    import anthropic

    client = client or anthropic.Anthropic()
    content: list = [{"type": "text", "text": f"The user's request: {request}\n\nWhat the app measured:\n"
                                              f"{json.dumps(facts, indent=1, default=str)}{i18n.instruction(lang)}"}]
    for label, frame in frames:
        content.append({"type": "text", "text": label})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _jpeg(frame)}})
    extra = {"output_config": {"effort": EFFORT}} if EFFORT else {}
    begin = time.monotonic()
    # "default" fallbacks: a declined request is retried server-side on Anthropic's recommended model.
    msg = client.beta.messages.parse(
        model=MODEL, max_tokens=16000, system=system_blocks(),
        messages=[{"role": "user", "content": content}], output_format=CoachReport,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default", **extra)
    timing.record_anthropic("coach call", msg, begin)
    if msg.stop_reason == "refusal":
        raise RuntimeError("the model declined to write the coaching")
    if msg.parsed_output is None:
        raise RuntimeError(f"no coaching came back (stop_reason={msg.stop_reason})")
    return msg.parsed_output, msg.model
