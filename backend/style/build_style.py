"""Turn data/style_ref/analysis/metrics.json into backend/style/swift_style.json.

The measured numbers come from analyze_refs.py; the layout, naming and coaching notes were
written by reading the contact sheets and the one available transcript. Everything is
described in our own words: no branding, logo, music or wording from the references.
Usage: cd backend && .venv/bin/python -m style.build_style"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
METRICS = HERE.parent / "data" / "style_ref" / "analysis" / "metrics.json"
OUT = HERE / "swift_style.json"


def _med(xs: list[float]) -> float | None:
    return round(float(np.median(xs)), 2) if xs else None


def measured(rows: list[dict]) -> dict:
    longs = [r for r in rows if r["kind"] == "videos"]
    shorts = [r for r in rows if r["kind"] == "shorts"]
    teach = [r for r in shorts if "HIGHLIGHTS" not in (r.get("title") or "").upper()]

    def summary(rs: list[dict]) -> dict:
        freezes = [f["dur"] for r in rs for f in r["freezes"]]
        slow = [s["end"] - s["start"] for r in rs for s in r["slowmo"]]
        dur = [r["duration_s"] for r in rs]
        frozen = [sum(f["dur"] for f in r["freezes"]) / r["duration_s"] for r in rs if r["duration_s"]]
        return {
            "videos": len(rs),
            "duration_s_median": _med(dur),
            "shot_length_s_median": _med([r["median_scene_s"] for r in rs if r["scenes"] > 1]),
            "freeze_frames_per_video_median": _med([len(r["freezes"]) for r in rs]),
            "freeze_hold_s_median": _med(freezes),
            "share_of_runtime_frozen_median": _med(frozen),
            "slowmo_stretch_s_median": _med(slow),
            "slowmo_stretches_per_video_median": _med([len(r["slowmo"]) for r in rs]),
        }

    return {"long_videos": summary(longs), "teaching_shorts": summary(teach),
            "highlight_shorts_skipped": len(shorts) - len(teach)}


def build() -> dict:
    rows = json.loads(METRICS.read_text())
    m = measured(rows)
    ts = m["teaching_shorts"]
    return {
        "about": ("Teaching-style profile measured from the 4 most recent long videos and the 10 most "
                  "recent Shorts of a table tennis coaching channel. The reference files stay in "
                  "backend/data/style_ref/ (git-ignored, never shown in the app). Only structure, pacing "
                  "and teaching approach are recorded here, in our own words."),
        "measured": m,
        "structure": {
            "short_form": ["hook", "phase 1", "phase 2", "phase 3", "recap"],
            "long_form": ["title + agenda of 3 parts", "numbered keys, one at a time", "slow motion at game "
                          "speed", "checklist recap", "one practice drill", "teaser for the next topic"],
            "step_count": 3,
            "notes": "Every phase is shown on the real motion first, then frozen on its key frame while "
                     "the cue is on screen. Comparisons stack two players and mark the good version "
                     "with a tick and the mistake with a cross.",
        },
        "pacing": {
            "hook_s": 2.0,
            "seconds_per_step": 3.0,
            "slowmo_lead_s": 0.6,
            "slowmo_factor": 0.5,
            "freeze_s": ts["freeze_hold_s_median"] or 1.5,
            "recap_s": 2.5,
            "practice_s": 2.0,
            "notes": "Teaching Shorts run 10-15 s: about 2 s of hook, 2.5-3 s per phase, 1.5-2.5 s of recap. "
                     "Long videos cut every ~5-6 s and spend about half their runtime on held frames of "
                     "about 1 s each, with ~1 s slow-motion stretches.",
        },
        "card_layout": {
            "header": "Persistent two-line title in the top-left: the stroke on line one, a short hook in "
                      "the accent colour on line two.",
            "cue": "Bottom third, under the footage: the phase cue in large condensed caps in that phase's "
                   "own colour, with one short plain sentence under it.",
            "numbering": "Small numbered chips (01, 02, 03) tie each cue to its place in the sequence.",
            "highlight": "The body part or bat path that the cue is about is drawn in the cue's colour "
                         "(glow, arrow or trail), so colour links words to motion.",
            "recap": "All cue words on one line joined with '+', each in its colour, plus one summary line.",
            "background": "Dark navy behind the footage; text never covers the player.",
        },
        "phase_naming": {
            "words": 2,
            "pattern": "Short imperative cue: an action plus a direction or body part, in caps "
                       "(for example our own LOAD LOW, LIFT THROUGH, END HIGH).",
            "colour_per_phase": True,
            "explanation_line": "One short sentence (about 4-7 words) saying what to look for.",
        },
        "coaching": {
            "principles": [
                "Number the keys and keep them to three or four.",
                "Pair every cue with the reason it works.",
                "Use concrete body landmarks: foot angle, knee bend, where the bat starts, shoulder turn.",
                "Explain the chain: legs, then hips, then chest, then arm, with the wrist last.",
                "Stay relaxed and accelerate into contact; tense only at the ball.",
                "Name one common mistake and its fix.",
                "Finish with a simple practice drill the player can do alone.",
            ],
            "tone": "Direct, second person, short sentences, no filler.",
        },
        "render": {
            "phase_colours_rgb": [[255, 107, 44], [56, 217, 245], [163, 230, 53]],
            "accent_rgb": [255, 107, 44],
            "notes": "TTSkill's own palette (ball orange first); the references' colours and fonts are not used.",
        },
    }


def main() -> None:
    OUT.write_text(json.dumps(build(), indent=2) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
