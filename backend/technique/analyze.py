"""Stage 1: turn sampled frames (or a text description) into a StrokeBreakdown.

Two analyzers share one interface:
  * ClaudeAnalyzer  - vision LLM (Anthropic) reads key frames + pose metrics, or the user's text.
  * OfflineAnalyzer - no network: fills a per-stroke coaching template from pose metrics.
`get_analyzer()` picks Claude when ANTHROPIC_API_KEY is set, else offline.
"""
from __future__ import annotations

import base64
import json
import os
from typing import Optional

import cv2
import numpy as np

from .schema import STROKES, Step, StrokeBreakdown, breakdown_json_schema

DEFAULT_MODEL = os.environ.get("TECHNIQUE_MODEL", "claude-sonnet-5-5")

SYSTEM = (
    "You are an elite table tennis coach who writes short, punchy coaching breakdowns for "
    "vertical social videos. Be concrete and technical (grip, stance, swing path, contact point, "
    "follow-through, recovery). Use plain words a club player understands. Never invent a player "
    "name that was not given. Lines must be short: at most ~45 characters each."
)


def _frame_jpegs(video: str, times: list[float], max_w: int = 960) -> list[tuple[float, str]]:
    cap = cv2.VideoCapture(video)
    out = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        if not ok:
            continue
        if f.shape[1] > max_w:
            f = cv2.resize(f, (max_w, int(f.shape[0] * max_w / f.shape[1])))
        ok, buf = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            out.append((t, base64.b64encode(buf.tobytes()).decode()))
    cap.release()
    return out


class ClaudeAnalyzer:
    name = "claude"

    def __init__(self, model: str = DEFAULT_MODEL, client=None):
        import anthropic

        self.model = model
        self.client = client or anthropic.Anthropic()

    def _call(self, content: list) -> StrokeBreakdown:
        tool = {
            "name": "submit_breakdown",
            "description": "Submit the structured stroke breakdown.",
            "input_schema": breakdown_json_schema(),
        }
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=SYSTEM,
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit_breakdown"},
            messages=[{"role": "user", "content": content}],
        )
        for block in msg.content:
            if getattr(block, "type", None) == "tool_use":
                data = dict(block.input)
                data["source"] = f"claude:{self.model}"
                return StrokeBreakdown.model_validate(data)
        raise RuntimeError("model did not return a breakdown")

    def from_video(self, video: str, stroke: str, frame_times: list[float], pose_summary: dict,
                   key_times: list[float], player: Optional[str] = None) -> StrokeBreakdown:
        content: list = [{
            "type": "text",
            "text": (
                f"Analyse the {stroke} technique of {player or 'the player nearest the camera'} "
                f"in these frames from a table tennis clip. Timestamps are seconds into the clip.\n"
                f"Pose metrics from MediaPipe (bat hand, swing peaks, joint angles):\n"
                f"{json.dumps(pose_summary)}\n"
                f"Suggested key moments (s): preparation {key_times[0]:.2f}, contact "
                f"{key_times[1]:.2f}, recovery {key_times[2]:.2f}. Use them for step key_time_s "
                f"unless the frames clearly show a better moment.\n"
                "Return exactly 3 steps: preparation, contact, recovery/finish."
            ),
        }]
        for t, b64 in _frame_jpegs(video, frame_times):
            content.append({"type": "text", "text": f"t={t:.2f}s"})
            content.append({"type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}})
        return self._call(content)

    def from_text(self, text: str, stroke: str, player: Optional[str] = None) -> StrokeBreakdown:
        return self._call([{
            "type": "text",
            "text": (
                f"Player: {player or 'unknown'}. Stroke: {stroke}.\n"
                f"Description of their training/technique from the user:\n{text}\n\n"
                "Write the breakdown. Leave key_time_s empty (null) for all 3 steps."
            ),
        }])


# ------------------------------------------------------------------ offline fallback

_TEMPLATES = {
    "forehand": dict(
        headline="Load low. Drive through.",
        grip="Shakehand grip, relaxed; index finger on the backhand rubber, thumb soft.",
        swing_path="Low-to-high and forward, turning the waist; bat closes over the ball.",
        follow_through="Bat finishes near the forehead, then snaps back to neutral.",
        steps=[("Load the bat side", ["Turn the waist back.", "Weight onto the back leg."],
                ["Turn the waist", "back leg"], ["WAIST TURN", "WEIGHT BACK"]),
               ("Drive through contact", ["Hit at the top of the bounce.", "Brush forward and up."],
                ["top of the bounce", "forward and up"], ["CONTACT IN FRONT"]),
               ("Recover to ready", ["Finish by the forehead.", "Reset feet for the next ball."],
                ["forehead", "Reset feet"], ["BACK TO READY"])]),
    "backhand": dict(
        headline="Elbow out. Flick it forward.",
        grip="Shakehand grip, thumb slightly up on the forehand side for backhand control.",
        swing_path="Short backswing to the belly, forearm opens forward from the elbow pivot.",
        follow_through="Bat finishes forward toward the target, elbow stays in front.",
        steps=[("Set the elbow", ["Bat in front of the belly.", "Keep the elbow forward."],
                ["in front", "elbow forward"], ["ELBOW IS THE PIVOT"]),
               ("Hit in front", ["Meet the ball early.", "Open the forearm fast."],
                ["early", "forearm"], ["BAT BEHIND BALL"]),
               ("Recover for the next", ["Relax the arm after contact.", "Stay square to the table."],
                ["Relax", "square"], ["BACK INTO POSITION"])]),
    "serve": dict(
        headline="Hide the spin. Keep it short.",
        grip="Loose shakehand, fingers relaxed so the wrist can whip.",
        swing_path="Fast brush across the bottom or side of the ball, low over the table.",
        follow_through="Short finish, bat back in front quickly for the third ball.",
        steps=[("Toss it straight", ["Open palm, 16 cm minimum.", "Watch the ball drop."],
                ["Open palm", "Watch the ball"], ["LEGAL TOSS"]),
               ("Brush, don't hit", ["Contact low, near the table.", "Accelerate the wrist."],
                ["Contact low", "wrist"], ["THIN CONTACT"]),
               ("Ready for ball three", ["Step back to neutral.", "Bat up in front."],
                ["neutral", "in front"], ["THIRD BALL READY"])]),
    "flick": dict(
        headline="Over the table. Snap the wrist.",
        grip="Shakehand, slightly looser so the wrist can cock back.",
        swing_path="Step in, cock the wrist, then a short sharp forward-up flick.",
        follow_through="Tiny finish, step back out of the table immediately.",
        steps=[("Step in under the ball", ["Right foot under the table.", "Get close to the bounce."],
                ["Right foot", "close"], ["STEP IN"]),
               ("Snap at the peak", ["Cock the wrist back.", "Flick forward over the top."],
                ["Cock the wrist", "over the top"], ["FAST FLICK"]),
               ("Get out of the table", ["Push off the front foot.", "Be ready for the fast ball."],
                ["Push off", "fast ball"], ["RECOVER"])]),
    "block": dict(
        headline="Quiet bat. Use their speed.",
        grip="Firm but not tight; bat angle closed against topspin.",
        swing_path="Almost no swing: bat meets the ball early and pushes slightly forward.",
        follow_through="Short and compact; reset the bat in front.",
        steps=[("Read the attack", ["Watch the opponent's bat.", "Set the angle early."],
                ["opponent's bat", "angle early"], ["READ THE LOOP"]),
               ("Meet it early", ["Contact just after the bounce.", "Keep the bat out front."],
                ["after the bounce", "out front"], ["BAT IN FRONT"]),
               ("Stay compact", ["Tiny follow-through.", "Bat back to neutral."],
                ["Tiny", "neutral"], ["KEEP THE RALLY ALIVE"])]),
    "footwork": dict(
        headline="Small steps. Always balanced.",
        grip="Neutral shakehand so either wing is ready.",
        swing_path="Move first, then swing: the body arrives before the bat.",
        follow_through="Push back to the centre after every shot.",
        steps=[("Split-step ready", ["Bounce on the balls of feet.", "Knees bent, weight forward."],
                ["balls of feet", "Knees bent"], ["READY STANCE"]),
               ("Move, then hit", ["Side-step to the ball.", "Arrive before you swing."],
                ["Side-step", "Arrive"], ["FEET FIRST"]),
               ("Recover to centre", ["Push off the outside leg.", "Back to the middle."],
                ["Push off", "middle"], ["BACK TO CENTRE"])]),
}


class OfflineAnalyzer:
    name = "offline"

    def _base(self, stroke: str, player: Optional[str], handed: str) -> dict:
        tpl = _TEMPLATES.get(stroke, _TEMPLATES["forehand"])
        return dict(player=player or "Player", stroke=stroke, handedness=handed,
                    headline=tpl["headline"], grip=tpl["grip"], swing_path=tpl["swing_path"],
                    follow_through=tpl["follow_through"])

    def _steps(self, stroke: str, key_times: list[Optional[float]]) -> list[Step]:
        tpl = _TEMPLATES.get(stroke, _TEMPLATES["forehand"])
        return [Step(title=t, lines=l, highlight_words=h, callouts=c, key_time_s=k)
                for (t, l, h, c), k in zip(tpl["steps"], key_times)]

    def from_video(self, video: str, stroke: str, frame_times: list[float], pose_summary: dict,
                   key_times: list[float], player: Optional[str] = None,
                   contact_metrics: Optional[dict] = None) -> StrokeBreakdown:
        # MediaPipe left/right labels are unreliable when the player faces away from the
        # camera, so the offline analyzer does not claim a handedness.
        b = self._base(stroke, player, "unknown")
        m = contact_metrics or {}
        knee = m.get("knee_angle_deg")
        width = m.get("stance_width_x_shoulders")
        elbow = m.get("elbow_angle_deg")
        wh = m.get("wrist_height_hip0_shoulder1")
        bend = ("deep knee bend" if knee and knee < 140 else
                "moderate knee bend" if knee and knee < 160 else "fairly upright legs")
        wide = ("wide base" if width and width > 1.6 else
                "shoulder-width base" if width and width > 0.9 else "narrow base")
        b["stance"] = f"{wide.capitalize()} with {bend}" + (f" (knees ~{knee} deg)." if knee else ".")
        if wh is None:
            height = "in front of the body"
        elif wh > 0.8:
            height = "around shoulder height"
        elif wh > 0.3:
            height = "between waist and chest"
        else:
            height = "low, near hip height"
        b["contact_point"] = (f"Ball met {height}, in front of the body"
                              + (f", elbow open to ~{elbow} deg." if elbow else "."))
        b["steps"] = self._steps(stroke, key_times)
        b["source"] = "offline-pose-template"
        return StrokeBreakdown.model_validate(b)

    def from_text(self, text: str, stroke: str, player: Optional[str] = None) -> StrokeBreakdown:
        b = self._base(stroke, player, "unknown")
        b["stance"] = "Athletic ready stance: feet a bit wider than shoulders, knees bent, weight forward."
        b["contact_point"] = "In front of the body at the top of the bounce."
        b["steps"] = self._steps(stroke, [None, None, None])
        b["source"] = "offline-text-template"
        return StrokeBreakdown.model_validate(b)


def get_analyzer(prefer: str = "auto"):
    """prefer: auto | claude | offline"""
    if prefer == "offline":
        return OfflineAnalyzer()
    if prefer == "claude" or (prefer == "auto" and os.environ.get("ANTHROPIC_API_KEY")):
        return ClaudeAnalyzer()
    return OfflineAnalyzer()


def normalize_stroke(s: str) -> str:
    s = (s or "").strip().lower()
    return s if s in STROKES else "forehand"
