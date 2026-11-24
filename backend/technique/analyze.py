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

import i18n

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

    def _call(self, content: list, lang: str = "en") -> StrokeBreakdown:
        # Structured output (the schema is the pydantic model) instead of a forced tool
        # call, which current models reject. "default" fallbacks retry a declined request
        # on Anthropic's recommended model inside the same call.
        import time

        import timing
        rule = i18n.instruction(lang)
        if rule:   # after the system prompt, in the user turn
            content = [*content, {"type": "text", "text": rule.strip()}]
        begin = time.monotonic()
        msg = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": content}],
            output_format=StrokeBreakdown,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        timing.record_anthropic("claude vision analyzer", msg, begin)
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
                   stroke_type: Optional[str] = None, detected: bool = False, lang: str = "en") -> StrokeBreakdown:
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
        return self._call(content, lang)

    def from_text(self, text: str, stroke: str, player: Optional[str] = None,
                  stroke_type: Optional[str] = None, detected: bool = False, lang: str = "en") -> StrokeBreakdown:
        return self._call([{
            "type": "text",
            "text": (
                f"Player: {player or 'unknown'}. {self._stroke_note(stroke, stroke_type, detected)}\n"
                f"Description of their training/technique from the user:\n{text}\n\n"
                "Write the breakdown. Leave key_time_s empty (null) for all 3 steps."
            ),
        }], lang)


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
    "backhand_block": _t(
        "Short and firm. Use their pace.",
        "Relaxed shakehand; bat in front of the body, angle closed over the ball.",
        "Almost no backswing: meet the ball early and push slightly forward from the forearm.",
        "Bat stays in front and resets at once; the next ball comes fast.",
        [("Bat ready", ["Bat in front before the bounce.", "No time to swing back against a loop."],
          ["in front", "No time"], ["READY EARLY"]),
         ("Firm angle", ["Close the bat over the ball.", "Their topspin does the work."],
          ["Close the bat", "topspin"], ["CLOSED ANGLE"]),
         ("Reset fast", ["Absorb, then back to ready.", "A short stroke keeps you in the rally."],
          ["Absorb", "ready"], ["COMPACT"])],
        "Bat ready, firm angle, reset fast.",
        "Partner loops to your backhand; block 30 back to the same spot."),
    "forehand_block": _t(
        "Bat in front. Meet it early.",
        "Shakehand; bat in front of the right hip (left hip for left-handers), angle closed.",
        "A short forward move from the forearm, meeting the ball just after the bounce.",
        "Stop the bat in front and recover to the ready position.",
        [("Bat ready", ["Bat out in front, knees bent.", "A big backswing is too late."],
          ["in front", "too late"], ["READY EARLY"]),
         ("Meet early", ["Contact just after the bounce.", "Their pace sends it back."],
          ["just after the bounce", "pace"], ["CLOSED ANGLE"]),
         ("Reset fast", ["Bat stops, back to ready.", "The next ball is already coming."],
          ["back to ready", "next ball"], ["COMPACT"])],
        "Bat ready, meet early, reset fast.",
        "Partner loops to your forehand; block 30, then mix in a counter-hit."),
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


# The same templates in Vietnamese (docs/glossary_vi.md): highlight words are copied from the lines,
# callouts are already in caps.
_TEMPLATES_VI = {
    "forehand_topspin": _t(
        "Hạ thấp. Vung lên qua bóng.",
        "Cầm ngang, thả lỏng; ngón trỏ dọc mặt trái tay, ngón cái mềm.",
        "Từ thấp lên cao và ra trước, lực từ chân và hông; mặt vợt úp qua đỉnh bóng.",
        "Vợt kết thúc gần trán, rồi nhanh chóng về tư thế chuẩn bị.",
        [("Hạ thấp", ["Dồn trọng tâm vào chân sau.", "Chân sau là nguồn lực."],
          ["chân sau", "nguồn lực"], ["TRỌNG TÂM SAU"]),
         ("Vung lên", ["Vợt bắt đầu dưới bóng.", "Giật cần quỹ đạo đi lên."],
          ["dưới bóng", "đi lên"], ["CHẠM BÓNG PHÍA TRƯỚC"]),
         ("Kết thúc cao", ["Vợt kết thúc ngang trán.", "Động tác gọn giúp về nhanh."],
          ["ngang trán", "về nhanh"], ["VỀ TƯ THẾ"])],
        "Hạ thấp, vung lên, kết thúc cao.",
        "Vung tay không 20 lần trước gương, kiểm tra từng điểm."),
    "forehand_drive": _t(
        "Lăng ngắn. Đánh xuyên bóng.",
        "Cầm ngang, chắc tay lúc chạm bóng; mặt vợt hơi úp.",
        "Lăng vợt ngắn về hông, rồi vung ra trước thẳng xuyên qua bóng.",
        "Kết thúc gọn trước mặt; về tư thế nhanh.",
        [("Lăng ngắn", ["Lăng vợt nhỏ về hông.", "Vung to sẽ bị muộn."],
          ["nhỏ", "muộn"], ["LĂNG VỢT NGẮN"]),
         ("Đánh xuyên", ["Chạm bóng ở điểm cao nhất.", "Đẩy ra trước, không lên trên."],
          ["điểm cao nhất", "ra trước"], ["MẶT VỢT HƠI ÚP"]),
         ("Về nhanh", ["Vợt dừng trước mũi.", "Sẵn sàng cho cú phản công."],
          ["trước mũi", "phản công"], ["GỌN GÀNG"])],
        "Lăng ngắn, đánh xuyên, về nhanh.",
        "Đôi công thuận tay 2 phút, đều và chắc."),
    "forehand_loop_backspin": _t(
        "Hạ thấp. Giật bóng xoáy xuống.",
        "Cầm ngang, lỏng khi lăng vợt để cổ tay thêm lực miết.",
        "Bắt đầu dưới mép bàn và vung dốc lên, miết lên phía sau bóng.",
        "Kết thúc cao trên đầu; chân đẩy bạn đứng lên lại.",
        [("Hạ thấp", ["Khuỵu gối, vợt dưới mặt bàn.", "Xoáy xuống kéo bóng đi xuống."],
          ["dưới mặt bàn", "đi xuống"], ["BẮT ĐẦU THẤP"]),
         ("Vung dốc", ["Miết lên phía sau bóng.", "Đợi bóng rơi sau điểm cao nhất."],
          ["phía sau bóng", "sau điểm cao nhất"], ["VUNG DỐC LÊN"]),
         ("Lên cao", ["Vợt kết thúc trên đầu.", "Chân đẩy bạn về tư thế."],
          ["trên đầu", "Chân"], ["KẾT THÚC CAO"])],
        "Hạ thấp, vung dốc, lên cao.",
        "Nhờ bạn gò dài và giật 10 quả liên tục."),
    "backhand_topspin": _t(
        "Khuỷu tay trước. Mở cẳng tay.",
        "Cầm ngang, ngón cái hơi cao hơn ở mặt thuận tay.",
        "Vợt về trước bụng, rồi cẳng tay mở ra trước và lên, khuỷu tay làm trục.",
        "Vợt kết thúc hướng về đích ngang tầm mắt; khuỷu tay ở phía trước.",
        [("Khuỷu trước", ["Vợt đặt trước bụng.", "Khuỷu tay là trục xoay."],
          ["trước bụng", "trục xoay"], ["KHUỶU TAY LÀM TRỤC"]),
         ("Mở tay", ["Cẳng tay mở ra trước và lên.", "Chạm bóng phía trước người."],
          ["ra trước và lên", "phía trước"], ["CHẠM BÓNG PHÍA TRƯỚC"]),
         ("Đứng vuông", ["Thả lỏng tay sau khi chạm.", "Đứng vuông bàn để kịp hai bên."],
          ["Thả lỏng", "hai bên"], ["VỀ TƯ THẾ"])],
        "Khuỷu trước, mở tay, đứng vuông.",
        "Đôi trái tay 50 quả, giữ khuỷu tay yên."),
    "backhand_flick": _t(
        "Bước vào. Vẩy qua đỉnh bóng.",
        "Cầm ngang, lỏng hơn một chút để cổ tay gập về sau.",
        "Bước chân vào gầm bàn, gập cổ tay về sau, rồi vẩy ngắn, nhanh ra trước và lên.",
        "Kết thúc nhỏ; lùi ra khỏi bàn ngay.",
        [("Bước vào", ["Chân bước vào gầm bàn.", "Đứng xa thì cổ tay không làm việc được."],
          ["gầm bàn", "cổ tay"], ["BƯỚC VÀO"]),
         ("Bật cổ tay", ["Gập cổ tay, rồi bật mạnh.", "Chạm bóng ở đỉnh nảy."],
          ["bật mạnh", "đỉnh nảy"], ["CỔ TAY NHANH"]),
         ("Lùi ra", ["Đẩy chân trước để lùi ra.", "Bóng trả về sẽ rất nhanh."],
          ["Đẩy chân trước", "rất nhanh"], ["VỀ TƯ THẾ"])],
        "Bước vào, bật cổ tay, lùi ra.",
        "Nhờ bạn giao ngắn; vẩy 10 quả, lùi về sau mỗi quả."),
    "backhand_push": _t(
        "Mở mặt vợt. Gò ngắn.",
        "Cầm ngang thả lỏng; mặt vợt mở hướng lên trần.",
        "Động tác ngắn ra trước và xuống dưới bóng, do cẳng tay dẫn.",
        "Vợt dừng thấp hướng về lưới; không vung lớn.",
        [("Mở mặt vợt", ["Mặt vợt ngửa lên trần.", "Mặt vợt mở xử lý được xoáy xuống."],
          ["ngửa lên trần", "xoáy xuống"], ["MỞ GÓC VỢT"]),
         ("Lướt dưới", ["Cẳng tay đưa ra trước và xuống.", "Chạm sớm, ngay sau khi bóng nảy."],
          ["ra trước và xuống", "sớm"], ["DƯỚI BÓNG"]),
         ("Giữ thấp", ["Kết thúc thấp hướng về lưới.", "Ở đây kiểm soát hơn sức mạnh."],
          ["thấp", "kiểm soát"], ["KIỂM SOÁT, KHÔNG DÙNG LỰC"])],
        "Mở mặt vợt, lướt dưới, giữ thấp.",
        "Gò trái tay chéo góc 30 quả."),
    "backhand_block": _t(
        "Ngắn và chắc. Mượn lực đối thủ.",
        "Cầm ngang thả lỏng; vợt trước người, mặt vợt úp qua bóng.",
        "Gần như không lăng vợt: chạm bóng sớm và đẩy nhẹ ra trước từ cẳng tay.",
        "Vợt ở phía trước và về ngay; quả tiếp theo đến rất nhanh.",
        [("Vợt sẵn", ["Vợt trước người trước khi nảy.", "Không kịp lăng vợt khi bị giật."],
          ["trước người", "Không kịp"], ["SẴN SÀNG SỚM"]),
         ("Góc chắc", ["Úp mặt vợt qua bóng.", "Xoáy lên của đối thủ làm phần việc."],
          ["Úp mặt vợt", "Xoáy lên"], ["MẶT VỢT ÚP"]),
         ("Về nhanh", ["Hấp thụ lực, rồi về tư thế.", "Động tác ngắn giữ bạn trong pha bóng."],
          ["Hấp thụ", "tư thế"], ["GỌN GÀNG"])],
        "Vợt sẵn, góc chắc, về nhanh.",
        "Nhờ bạn giật vào trái tay; chặn 30 quả về cùng một điểm."),
    "forehand_block": _t(
        "Vợt phía trước. Chạm sớm.",
        "Cầm ngang; vợt trước hông phải (hông trái với người thuận tay trái), mặt vợt úp.",
        "Đưa cẳng tay ra trước một đoạn ngắn, chạm bóng ngay sau khi nảy.",
        "Dừng vợt ở phía trước và về tư thế chuẩn bị.",
        [("Vợt sẵn", ["Vợt ra trước, khuỵu gối.", "Lăng vợt lớn là quá muộn."],
          ["ra trước", "quá muộn"], ["SẴN SÀNG SỚM"]),
         ("Chạm sớm", ["Chạm ngay sau khi bóng nảy.", "Lực của đối thủ đưa bóng về."],
          ["ngay sau khi bóng nảy", "Lực"], ["MẶT VỢT ÚP"]),
         ("Về nhanh", ["Vợt dừng, về tư thế.", "Quả tiếp theo đã đến rồi."],
          ["về tư thế", "Quả tiếp theo"], ["GỌN GÀNG"])],
        "Vợt sẵn, chạm sớm, về nhanh.",
        "Nhờ bạn giật vào thuận tay; chặn 30 quả, rồi xen kẽ phản công."),
    "chop": _t(
        "Từ cao xuống thấp. Cắt dưới bóng.",
        "Cầm ngang, cổ tay chắc; mặt vợt mở.",
        "Từ ngang vai đi xuống và ra trước, cắt dưới bóng khi bóng rơi.",
        "Vợt kết thúc thấp cạnh đầu gối; bước vào lại cho quả sau.",
        [("Vợt cao", ["Lùi lại, vợt ngang vai.", "Độ cao cho bạn khoảng để cắt xuống."],
          ["ngang vai", "cắt xuống"], ["BẮT ĐẦU CAO"]),
         ("Cắt xuống", ["Đợi bóng rơi xuống trước.", "Cắt dưới phía sau bóng."],
          ["rơi xuống", "dưới"], ["MẶT VỢT MỞ"]),
         ("Kết thúc thấp", ["Vợt kết thúc gần đầu gối.", "Bước nhỏ vào lại cho quả sau."],
          ["đầu gối", "Bước nhỏ"], ["KIỂM SOÁT XOÁY XUỐNG"])],
        "Vợt cao, cắt xuống, kết thúc thấp.",
        "Nhờ bạn giật nhẹ; cắt 10 quả về sâu."),
    "serve": _t(
        "Giấu xoáy. Giao ngắn.",
        "Cầm ngang lỏng, ngón tay thả lỏng để cổ tay bật nhanh.",
        "Miết nhanh ngang đáy hoặc cạnh bóng, thấp sát mặt bàn.",
        "Kết thúc ngắn, đưa vợt về trước nhanh cho bóng thứ ba.",
        [("Tung thẳng", ["Mở lòng bàn tay, tung cao từ 16 cm.", "Tung đúng luật giữ được điểm."],
          ["Mở lòng bàn tay", "đúng luật"], ["TUNG BÓNG ĐÚNG LUẬT"]),
         ("Miết mỏng", ["Chạm bóng thấp, sát mặt bàn.", "Chạm mỏng mới tạo xoáy."],
          ["thấp", "Chạm mỏng"], ["CHẠM MỎNG"]),
         ("Bóng thứ ba", ["Về tư thế trung lập thật nhanh.", "Bóng trả về đến rất nhanh."],
          ["trung lập", "rất nhanh"], ["SẴN SÀNG BÓNG THỨ BA"])],
        "Tung thẳng, miết mỏng, sẵn sàng bóng thứ ba.",
        "Giao 20 quả vào một điểm, chỉ đổi loại xoáy."),
    "block": _t(
        "Vợt êm. Mượn tốc độ đối thủ.",
        "Chắc nhưng không gồng; mặt vợt úp khi gặp bóng xoáy lên.",
        "Gần như không vung: vợt chạm bóng sớm và đẩy nhẹ ra trước.",
        "Ngắn và gọn; đưa vợt về lại phía trước.",
        [("Đọc bóng", ["Nhìn vợt của đối thủ.", "Góc vợt cho biết loại xoáy."],
          ["vợt của đối thủ", "xoáy"], ["ĐỌC CÚ GIẬT"]),
         ("Chạm sớm", ["Chạm ngay sau khi bóng nảy.", "Dùng tốc độ của họ, không phải của bạn."],
          ["sau khi bóng nảy", "tốc độ của họ"], ["VỢT PHÍA TRƯỚC"]),
         ("Giữ êm", ["Vung theo thật nhỏ.", "Vung lớn sẽ làm bóng đi dài."],
          ["thật nhỏ", "đi dài"], ["GIỮ PHA BÓNG"])],
        "Đọc bóng, chạm sớm, giữ êm.",
        "Nhờ bạn giật; chặn 30 quả vào một góc."),
    "footwork": _t(
        "Bước nhỏ. Luôn thăng bằng.",
        "Cầm ngang trung lập để sẵn sàng cả hai bên.",
        "Di chuyển trước, vung sau: người đến trước vợt.",
        "Đẩy về giữa sau mỗi cú đánh.",
        [("Nhún bật", ["Nhún trên mũi bàn chân.", "Bạn bắt đầu di chuyển sớm hơn."],
          ["mũi bàn chân", "sớm hơn"], ["TƯ THẾ SẴN SÀNG"]),
         ("Chân trước", ["Bước ngang đến bóng.", "Đến nơi rồi mới vung."],
          ["Bước ngang", "Đến nơi"], ["DI CHUYỂN RỒI ĐÁNH"]),
         ("Về giữa", ["Đẩy bằng chân phía ngoài.", "Về giữa sau mỗi cú."],
          ["Đẩy", "giữa"], ["VỀ GIỮA"])],
        "Nhún bật, chân trước, về giữa.",
        "Bài tập bộ chân hai điểm: thuận tay, trái tay, 2 phút."),
}
_TEMPLATES_VI.update(forehand=_TEMPLATES_VI["forehand_topspin"], backhand=_TEMPLATES_VI["backhand_topspin"],
                     flick=_TEMPLATES_VI["backhand_flick"])
TEMPLATES = {"en": _TEMPLATES, "vi": _TEMPLATES_VI}

# The offline analyzer's measured sentences.
_MEASURED = {
    "en": dict(no_legs="Legs out of frame, so the stance isn't measured.",
               deep="deep knee bend", moderate="moderate knee bend", upright="fairly upright legs",
               wide="wide base", shoulder="shoulder-width base", narrow="narrow base",
               stance="{wide} with {bend} (knees ~{knee} deg).",
               front="in front of the body", shoulder_h="around shoulder height",
               waist="between waist and chest", low="low, near hip height",
               contact="Ball met {height}, in front of the body", elbow=", elbow open to ~{elbow} deg.",
               text_stance="Athletic ready stance: feet a bit wider than shoulders, knees bent, weight forward.",
               text_contact="In front of the body at the top of the bounce."),
    "vi": dict(no_legs="Chân ra ngoài khung hình nên chưa đo được tư thế đứng.",
               deep="khuỵu gối sâu", moderate="khuỵu gối vừa phải", upright="chân khá thẳng",
               wide="Chân đứng rộng", shoulder="Chân rộng bằng vai", narrow="Chân đứng hẹp",
               stance="{wide}, {bend} (gối ~{knee}°).",
               front="phía trước người", shoulder_h="ngang vai", waist="giữa eo và ngực",
               low="thấp, gần ngang hông",
               contact="Chạm bóng {height}, phía trước người", elbow=", khuỷu tay mở ~{elbow}°.",
               text_stance="Tư thế sẵn sàng: chân rộng hơn vai một chút, khuỵu gối, trọng tâm dồn ra trước.",
               text_contact="Phía trước người, ở đỉnh nảy của bóng."),
}


class OfflineAnalyzer:
    name = "offline"

    @staticmethod
    def _template(stroke: str, stroke_type: Optional[str], lang: str = "en") -> dict:
        tpls = TEMPLATES[i18n.norm(lang)]
        return tpls.get(stroke_type or "") or tpls.get(stroke) or tpls["forehand"]

    def _base(self, stroke: str, player: Optional[str], handed: str,
              stroke_type: Optional[str] = None, lang: str = "en") -> dict:
        tpl = self._template(stroke, stroke_type, lang)
        return dict(player=player or "Player", stroke=stroke, stroke_type=stroke_type,
                    handedness=handed, headline=tpl["headline"], grip=tpl["grip"],
                    swing_path=tpl["swing_path"], follow_through=tpl["follow_through"],
                    recap=tpl["recap"], drill=tpl["drill"])

    def _steps(self, stroke: str, key_times: list[Optional[float]],
               stroke_type: Optional[str] = None, lang: str = "en") -> list[Step]:
        tpl = self._template(stroke, stroke_type, lang)
        return [Step(title=t, lines=l, highlight_words=h, callouts=c, key_time_s=k)
                for (t, l, h, c), k in zip(tpl["steps"], key_times)]

    def from_video(self, video: str, stroke: str, frame_times: list[float], pose_summary: dict,
                   key_times: list[float], player: Optional[str] = None,
                   contact_metrics: Optional[dict] = None, stroke_type: Optional[str] = None,
                   detected: bool = False, lang: str = "en") -> StrokeBreakdown:
        # MediaPipe left/right labels are unreliable when the player faces away from the
        # camera, so the offline analyzer does not claim a handedness.
        b = self._base(stroke, player, "unknown", stroke_type, lang)
        w = _MEASURED[i18n.norm(lang)]
        m = contact_metrics or {}
        knee = m.get("knee_angle_deg")
        width = m.get("stance_width_x_shoulders")
        elbow = m.get("elbow_angle_deg")
        wh = m.get("wrist_height_hip0_shoulder1")
        if knee is None or width is None:
            b["stance"] = w["no_legs"]
        else:
            bend = w["deep"] if knee < 140 else w["moderate"] if knee < 160 else w["upright"]
            wide = w["wide"] if width > 1.6 else w["shoulder"] if width > 0.9 else w["narrow"]
            b["stance"] = w["stance"].format(wide=wide[0].upper() + wide[1:], bend=bend, knee=knee)
        if wh is None:
            height = w["front"]
        elif wh > 0.8:
            height = w["shoulder_h"]
        elif wh > 0.3:
            height = w["waist"]
        else:
            height = w["low"]
        b["contact_point"] = (w["contact"].format(height=height)
                              + (w["elbow"].format(elbow=elbow) if elbow else "."))
        b["steps"] = self._steps(stroke, key_times, stroke_type, lang)
        b["source"] = "offline-pose-template"
        return StrokeBreakdown.model_validate(b)

    def from_text(self, text: str, stroke: str, player: Optional[str] = None,
                  stroke_type: Optional[str] = None, detected: bool = False, lang: str = "en") -> StrokeBreakdown:
        w = _MEASURED[i18n.norm(lang)]
        b = self._base(stroke, player, "unknown", stroke_type, lang)
        b["stance"] = w["text_stance"]
        b["contact_point"] = w["text_contact"]
        b["steps"] = self._steps(stroke, [None, None, None], stroke_type, lang)
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
