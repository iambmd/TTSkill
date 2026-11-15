"""Teaching-style profile (backend/style/swift_style.json): pacing and colours for the
renderer, and the naming/coaching guide that goes into the Claude prompt."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "style" / "swift_style.json"

_FALLBACK = {
    "pacing": {"hook_s": 2.0, "seconds_per_step": 3.0, "slowmo_lead_s": 0.6, "slowmo_factor": 0.5,
               "freeze_s": 1.5, "recap_s": 2.5, "practice_s": 2.0},
    "structure": {"step_count": 3},
    "phase_naming": {"words": 2, "pattern": "action plus a direction or body part, in caps",
                     "explanation_line": "one short sentence saying what to look for"},
    "coaching": {"principles": [], "tone": "Direct, second person, short sentences."},
    "render": {"phase_colours_rgb": [[255, 107, 44], [56, 217, 245], [163, 230, 53]],
               "accent_rgb": [255, 107, 44]},
}


@lru_cache(None)
def profile() -> dict:
    try:
        data = json.loads(PATH.read_text())
    except (OSError, ValueError):
        return _FALLBACK
    return {k: data.get(k, v) for k, v in _FALLBACK.items()} | data


def pacing() -> dict:
    return {**_FALLBACK["pacing"], **profile().get("pacing", {})}


def phase_colours() -> list[tuple[int, int, int]]:
    return [tuple(c) for c in profile()["render"]["phase_colours_rgb"]]


def accent() -> tuple[int, int, int]:
    return tuple(profile()["render"]["accent_rgb"])


def prompt_guide() -> str:
    """Style rules for the Claude prompt, built from the profile."""
    p = profile()
    naming, coaching = p["phase_naming"], p["coaching"]
    rules = [
        f"Exactly {p['structure'].get('step_count', 3)} steps in time order.",
        f"Each step title is a {naming.get('words', 2)}-word cue. {str(naming.get('pattern', '')).rstrip('.')}.",
        "Line 1 says what to look for; line 2 gives the reason it works or the mistake it prevents.",
        "recap joins the three cues into one line; drill is one simple practice drill a player can do alone.",
        *coaching.get("principles", []),
        coaching.get("tone", ""),
    ]
    return "Style guide:\n" + "\n".join(f"- {r}" for r in rules if r)
