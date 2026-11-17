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

from .schema import STROKES, Step, StrokeBreakdown
from .strokes import STROKE_TYPES
from .style import prompt_guide

DEFAULT_MODEL = os.environ.get("TECHNIQUE_MODEL", "claude-opus-5-5")

SYSTEM = (
    "You are an elite table tennis coach who writes short, punchy coaching breakdowns for "
    "vertical social videos. Be concrete and technical (grip, stance, swing path, contact point, "
    "follow-through, recovery). Use plain words a club player understands. Never invent a player "
    "name that was not given. Lines must be short: at most ~45 characters each. Write everything "
    "in your own words.\n\n" + prompt_guide()
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
        # Structured output (the schema is the pydantic model) instead of a forced tool
        # call, which current models reject. "default" fallbacks retry a declined request
        # on Anthropic's recommended model inside the same call.
        msg = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": content}],
            output_format=StrokeBreakdown,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if msg.stop_reason == "refusal":
            raise RuntimeError("model declined the request")
        b = msg.parsed_output
        if b is None:
            raise RuntimeError(f"model did not return a breakdown (stop_reason={msg.stop_reason})")
        b.source = f"claude:{msg.model}"
        return b

    @staticmethod
    def _stroke_note(stroke: str, stroke_type: Optional[str], detected: bool) -> str:
        st = STROKE_TYPES.get(stroke_type or "")
        if not st:
            return f"Stroke: {stroke}."
        how = ("auto-detected from the pose; if the frames clearly show a different stroke, "
               "set stroke_type to the right one" if detected else "chosen by the user")
        return (f"Stroke type: {st.label} ({how}). What matters for this stroke: {st.focus}. "
                f"Base the 3 steps on its phases: {', '.join(st.phases)}. "
                f"Set stroke to {st.stroke!r} and stroke_type to {st.key!r} unless you correct it.")

    def from_video(self, video: str, stroke: str, frame_times: list[float], pose_summary: dict,
                   key_times: list[float], player: Optional[str] = None,
                   stroke_type: Optional[str] = None, detected: bool = False) -> StrokeBreakdown:
        content: list = [{
            "type": "text",
            "text": (
                f"Analyse the {stroke} technique of {player or 'the player nearest the camera'} "
                f"in these frames from a table tennis clip. Timestamps are seconds into the clip.\n"
                f"{self._stroke_note(stroke, stroke_type, detected)}\n"
                f"Pose metrics from MediaPipe (bat hand, swing peaks, joint angles):\n"
                f"{json.dumps(pose_summary)}\n"
                f"Suggested key moments (s): preparation {key_times[0]:.2f}, contact "
                f"{key_times[1]:.2f}, recovery {key_times[2]:.2f}. Use them for step key_time_s "
                f"unless the frames clearly show a better moment.\n"
                "Return exactly 3 steps in time order: preparation, contact, recovery/finish."
            ),
        }]
        for t, b64 in _frame_jpegs(video, frame_times):
            content.append({"type": "text", "text": f"t={t:.2f}s"})
            content.append({"type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}})
        return self._call(content)

    def from_text(self, text: str, stroke: str, player: Optional[str] = None,
                  stroke_type: Optional[str] = None, detected: bool = False) -> StrokeBreakdown:
        return self._call([{
            "type": "text",
            "text": (
                f"Player: {player or 'unknown'}. {self._stroke_note(stroke, stroke_type, detected)}\n"
                f"Description of their training/technique from the user:\n{text}\n\n"
                "Write the breakdown. Leave key_time_s empty (null) for all 3 steps."
            ),
        }])


# ------------------------------------------------------------------ offline fallback

# One coaching template per stroke type (strokes.STROKE_TYPES) plus block and footwork.
# Shape follows style/swift_style.json: 3 two-word cues; line 1 = what to look for,
# line 2 = why it works or the mistake it prevents; a recap line and a practice drill.
# Original wording.
def _t(headline, grip, swing_path, follow_through, steps, recap, drill):
    return dict(headline=headline, grip=grip, swing_path=swing_path, follow_through=follow_through,
                steps=steps, recap=recap, drill=drill)


_TEMPLATES = {
    "forehand_topspin": _t(
        "Load low. Swing up through it.",
        "Shakehand, relaxed; index finger along the backhand rubber, thumb soft.",
        "Low-to-high and forward, driven by the legs and waist; bat closes over the top.",
        "Bat finishes near the forehead, then snaps back to ready.",
        [("Load low", ["Weight sinks onto the back leg.", "That loaded leg is your power."],
          ["back leg", "power"], ["WEIGHT BACK"]),
         ("Lift through", ["Bat starts below the ball.", "Topspin needs an upward path."],
          ["below the ball", "upward"], ["CONTACT IN FRONT"]),
         ("End high", ["Bat finishes by the forehead.", "A short finish resets faster."],
          ["forehead", "resets faster"], ["BACK TO READY"])],
        "Load low, lift through, end high.",
        "Shadow 20 swings in a mirror, checking each cue."),
    "forehand_drive": _t(
        "Stay short. Hit through it.",
        "Shakehand, firm at contact; bat face slightly closed.",
        "Short backswing to the hip, then a flatter forward swing straight through the ball.",
        "Compact finish in front of the face; recover quickly.",
        [("Stay short", ["Small backswing to the hip.", "A big swing arrives late."],
          ["Small backswing", "late"], ["SHORT BACKSWING"]),
         ("Hit through", ["Meet the ball at the peak.", "Drive forward, not upward."],
          ["peak", "forward"], ["BAT SLIGHTLY CLOSED"]),
         ("Snap back", ["Bat stops in front of your nose.", "You are ready for the counter."],
          ["nose", "counter"], ["STAY COMPACT"])],
        "Stay short, hit through, snap back.",
        "Rally forehand to forehand for 2 minutes, flat and steady."),
    "forehand_loop_backspin": _t(
        "Get low. Lift the backspin.",
        "Shakehand, loose in the backswing so the wrist can add brush.",
        "Start below the table edge and swing steeply up, brushing up the back of the ball.",
        "High finish above the head; the legs push you back up.",
        [("Drop low", ["Knees bend, bat below the table.", "Backspin pulls the ball down."],
          ["below the table", "down"], ["LOW START"]),
         ("Lift steep", ["Swing up the back of the ball.", "Let it drop after the peak."],
          ["up the back", "after the peak"], ["STEEP UPWARD SWING"]),
         ("End above", ["Bat finishes above your head.", "Legs push you back to ready."],
          ["above your head", "Legs"], ["FINISH HIGH"])],
        "Drop low, lift steep, end above.",
        "Have a partner push long and loop 10 in a row."),
    "backhand_topspin": _t(
        "Elbow forward. Open the forearm.",
        "Shakehand with the thumb a little higher on the forehand side.",
        "Bat back to the belly, then the forearm opens forward and up from an elbow pivot.",
        "Bat finishes toward the target at eye level; elbow stays in front.",
        [("Elbow forward", ["Bat sits in front of the belly.", "The elbow is the pivot."],
          ["belly", "pivot"], ["ELBOW IS THE PIVOT"]),
         ("Open out", ["Forearm opens forward and up.", "Meet the ball in front of you."],
          ["forward and up", "in front"], ["CONTACT IN FRONT"]),
         ("Stay square", ["Relax the arm after contact.", "Square stance covers both wings."],
          ["Relax", "both wings"], ["BACK TO READY"])],
        "Elbow forward, open out, stay square.",
        "Backhand-to-backhand rally, 50 balls, elbow still."),
    "backhand_flick": _t(
        "Step in. Snap it over the top.",
        "Shakehand, slightly looser so the wrist can cock back.",
        "Step under the table, cock the wrist back, then a short sharp flick forward and up.",
        "Tiny finish; push back out of the table straight away.",
        [("Step in", ["Foot goes under the table.", "Too far away and the wrist can't work."],
          ["under the table", "wrist"], ["STEP IN"]),
         ("Wrist snap", ["Cock the wrist, then whip it.", "Contact at the top of the bounce."],
          ["whip", "top of the bounce"], ["FAST WRIST"]),
         ("Step out", ["Push off the front foot.", "A fast return is coming."],
          ["Push off", "fast return"], ["RECOVER"])],
        "Step in, wrist snap, step out.",
        "Partner serves short; flick 10, recovering after each."),
    "backhand_push": _t(
        "Open bat. Keep it short.",
        "Relaxed shakehand; bat face open toward the ceiling.",
        "Short forward-and-down stroke under the ball, guided by the forearm.",
        "Bat stops low toward the net; no big swing.",
        [("Open face", ["Bat face tilts to the ceiling.", "An open bat handles the backspin."],
          ["ceiling", "backspin"], ["OPEN ANGLE"]),
         ("Glide under", ["Forearm moves forward and down.", "Contact early, just after the bounce."],
          ["forward and down", "early"], ["UNDER THE BALL"]),
         ("Stay low", ["Finish low toward the net.", "Control beats power here."],
          ["low", "Control"], ["CONTROL, NOT POWER"])],
        "Open face, glide under, stay low.",
        "Push rally on the backhand diagonal, 30 balls."),
    "chop": _t(
        "High to low. Cut under it.",
        "Shakehand, firm wrist; bat face open.",
        "From shoulder height down and forward, cutting under the ball as it drops.",
        "Bat ends low by the knee; step back in for the next ball.",
        [("Bat high", ["Step back, bat by the shoulder.", "Height gives room to cut down."],
          ["shoulder", "cut down"], ["HIGH START"]),
         ("Cut down", ["Let the ball drop first.", "Slice under the back of it."],
          ["drop", "under"], ["OPEN BAT FACE"]),
         ("Low finish", ["Bat ends near the knee.", "Shuffle back in for the next ball."],
          ["knee", "Shuffle"], ["BACKSPIN CONTROL"])],
        "Bat high, cut down, low finish.",
        "Partner loops gently; chop 10 back deep."),
    "serve": _t(
        "Hide the spin. Keep it short.",
        "Loose shakehand, fingers relaxed so the wrist can whip.",
        "Fast brush across the bottom or side of the ball, low over the table.",
        "Short finish, bat back in front quickly for the third ball.",
        [("Toss straight", ["Open palm, at least 16 cm up.", "A legal toss wins the first point."],
          ["Open palm", "legal"], ["LEGAL TOSS"]),
         ("Graze it", ["Contact low, near the table.", "A thin contact makes the spin."],
          ["low", "thin contact"], ["THIN CONTACT"]),
         ("Ball three", ["Step back to neutral fast.", "The return comes quickly."],
          ["neutral", "quickly"], ["THIRD BALL READY"])],
        "Toss straight, graze it, ready for ball three.",
        "Serve 20 balls to one target, changing only the spin."),
    "block": _t(
        "Quiet bat. Use their speed.",
        "Firm but not tight; bat angle closed against topspin.",
        "Almost no swing: bat meets the ball early and pushes slightly forward.",
        "Short and compact; reset the bat in front.",
        [("Read it", ["Watch the opponent's bat.", "Its angle tells you the spin."],
          ["opponent's bat", "spin"], ["READ THE LOOP"]),
         ("Meet early", ["Contact just after the bounce.", "Use their speed, not yours."],
          ["after the bounce", "their speed"], ["BAT IN FRONT"]),
         ("Stay quiet", ["Tiny follow-through.", "A big swing sends it long."],
          ["Tiny", "long"], ["KEEP THE RALLY ALIVE"])],
        "Read it, meet early, stay quiet.",
        "Partner loops; block 30 balls to one corner."),
    "footwork": _t(
        "Small steps. Always balanced.",
        "Neutral shakehand so either wing is ready.",
        "Move first, then swing: the body arrives before the bat.",
        "Push back to the centre after every shot.",
        [("Split step", ["Bounce on the balls of your feet.", "You start moving sooner."],
          ["balls of your feet", "sooner"], ["READY STANCE"]),
         ("Feet first", ["Side-step to the ball.", "Arrive before you swing."],
          ["Side-step", "Arrive"], ["MOVE, THEN HIT"]),
         ("Back centre", ["Push off the outside leg.", "Reset to the middle every shot."],
          ["Push off", "middle"], ["BACK TO CENTRE"])],
        "Split step, feet first, back to centre.",
        "Two-point footwork drill: forehand, backhand, 2 minutes."),
}
# Older broad strokes reuse the matching type's template.
_TEMPLATES.update(forehand=_TEMPLATES["forehand_topspin"], backhand=_TEMPLATES["backhand_topspin"],
                  flick=_TEMPLATES["backhand_flick"])


class OfflineAnalyzer:
    name = "offline"

    @staticmethod
    def _template(stroke: str, stroke_type: Optional[str]) -> dict:
        return _TEMPLATES.get(stroke_type or "") or _TEMPLATES.get(stroke) or _TEMPLATES["forehand"]

    def _base(self, stroke: str, player: Optional[str], handed: str,
              stroke_type: Optional[str] = None) -> dict:
        tpl = self._template(stroke, stroke_type)
        return dict(player=player or "Player", stroke=stroke, stroke_type=stroke_type,
                    handedness=handed, headline=tpl["headline"], grip=tpl["grip"],
                    swing_path=tpl["swing_path"], follow_through=tpl["follow_through"],
                    recap=tpl["recap"], drill=tpl["drill"])

    def _steps(self, stroke: str, key_times: list[Optional[float]],
               stroke_type: Optional[str] = None) -> list[Step]:
        tpl = self._template(stroke, stroke_type)
        return [Step(title=t, lines=l, highlight_words=h, callouts=c, key_time_s=k)
                for (t, l, h, c), k in zip(tpl["steps"], key_times)]

    def from_video(self, video: str, stroke: str, frame_times: list[float], pose_summary: dict,
                   key_times: list[float], player: Optional[str] = None,
                   contact_metrics: Optional[dict] = None, stroke_type: Optional[str] = None,
                   detected: bool = False) -> StrokeBreakdown:
        # MediaPipe left/right labels are unreliable when the player faces away from the
        # camera, so the offline analyzer does not claim a handedness.
        b = self._base(stroke, player, "unknown", stroke_type)
        m = contact_metrics or {}
        knee = m.get("knee_angle_deg")
        width = m.get("stance_width_x_shoulders")
        elbow = m.get("elbow_angle_deg")
        wh = m.get("wrist_height_hip0_shoulder1")
        if knee is None or width is None:
            b["stance"] = "Legs out of frame, so the stance isn't measured."
        else:
            bend = ("deep knee bend" if knee < 140 else
                    "moderate knee bend" if knee < 160 else "fairly upright legs")
            wide = ("wide base" if width > 1.6 else
                    "shoulder-width base" if width > 0.9 else "narrow base")
            b["stance"] = f"{wide.capitalize()} with {bend} (knees ~{knee} deg)."
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
        b["steps"] = self._steps(stroke, key_times, stroke_type)
        b["source"] = "offline-pose-template"
        return StrokeBreakdown.model_validate(b)

    def from_text(self, text: str, stroke: str, player: Optional[str] = None,
                  stroke_type: Optional[str] = None, detected: bool = False) -> StrokeBreakdown:
        b = self._base(stroke, player, "unknown", stroke_type)
        b["stance"] = "Athletic ready stance: feet a bit wider than shoulders, knees bent, weight forward."
        b["contact_point"] = "In front of the body at the top of the bounce."
        b["steps"] = self._steps(stroke, [None, None, None], stroke_type)
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
