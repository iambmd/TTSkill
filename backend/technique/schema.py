"""Structured stroke breakdown: the contract between analysis, prompting and rendering."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Stroke = Literal["forehand", "backhand", "serve", "flick", "block", "footwork", "chop"]
STROKES: tuple[str, ...] = ("forehand", "backhand", "serve", "flick", "block", "footwork", "chop")


class Step(BaseModel):
    title: str = Field(description="Two-word cue: an action plus a direction or body part, e.g. 'Load low'")
    lines: List[str] = Field(description="Exactly two short lines (max ~45 chars each): what to look "
                                         "for, then why it works or the mistake it prevents")
    highlight_words: List[str] = Field(
        default_factory=list, description="Words/phrases from `lines` to show in the accent color"
    )
    key_time_s: Optional[float] = Field(
        default=None, description="Seconds into the analysed clip where this step is best shown"
    )
    callouts: List[str] = Field(
        default_factory=list, description="1-2 tiny ALL-CAPS labels, e.g. 'BAT BEHIND BALL'"
    )


class StrokeBreakdown(BaseModel):
    player: str = Field(default="Player", description="Player name if known")
    stroke: str = Field(description="One of forehand, backhand, serve, flick, block, footwork, chop")
    stroke_type: Optional[str] = Field(
        default=None,
        description="Specific stroke: forehand_topspin, forehand_drive, forehand_loop_backspin, "
                    "backhand_topspin, backhand_flick, backhand_push, chop, serve; null if unknown",
    )
    handedness: Literal["right", "left", "unknown"] = "unknown"
    headline: str = Field(description="3-6 word hook, e.g. 'Stretched wide? Counter and recover.'")
    grip: str = Field(description="Grip style and how it is held for this stroke")
    stance: str = Field(description="Feet, knee bend, body angle to the table")
    swing_path: str = Field(description="Backswing -> forward swing path, low-to-high etc.")
    contact_point: str = Field(description="Where/when the bat meets the ball relative to the body and bounce")
    follow_through: str = Field(description="Finish position and recovery")
    steps: List[Step] = Field(description="Exactly three numbered coaching steps in time order")
    recap: Optional[str] = Field(default=None, description="One line joining the three cues, e.g. 'Load low, lift through, end high.'")
    drill: Optional[str] = Field(default=None, description="One simple practice drill the player can do alone")
    source: str = Field(default="unknown", description="Which analyzer produced this")


def breakdown_json_schema() -> dict:
    return StrokeBreakdown.model_json_schema()
