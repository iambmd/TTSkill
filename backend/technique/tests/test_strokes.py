"""Stroke types: detection from synthetic swings, direction-aware key moments, templates,
text detection, and the Claude request shape (mocked HTTP, no network)."""
import json

import httpx2 as httpx
import numpy as np
import pytest

from technique import strokes
from technique.analyze import ClaudeAnalyzer, OfflineAnalyzer
from technique.pipeline import key_moments, run_text
from technique.pose import PoseTrack

FPS, N, C = 30.0, 90, 45  # contact at frame 45 (1.5 s)


def _track(wx, wy) -> PoseTrack:
    """Upright player seen from behind (their right = image right). The right wrist follows
    wx(t), wy(t) in normalised coords; contact (the fastest point) is at frame C."""
    lm = np.zeros((N, 33, 4), np.float32)
    lm[:, :, 3] = 1
    base = {0: (.5, .2), 11: (.45, .3), 12: (.55, .3), 13: (.42, .4), 14: (.58, .4),
            15: (.40, .5), 16: (.60, .5), 23: (.47, .55), 24: (.53, .55), 25: (.46, .7),
            26: (.54, .7), 27: (.45, .9), 28: (.55, .9)}
    for j, (x, y) in base.items():
        lm[:, j, 0], lm[:, j, 1] = x, y
    t = np.arange(N, dtype=np.float32)
    lm[:, 16, 0], lm[:, 16, 1] = wx(t), wy(t)
    return PoseTrack(fps=FPS, width=1280, height=720, times=t / FPS, lm=lm,
                     world=np.zeros((N, 33, 3), np.float32))


def _sweep(a, b, width=6.0):
    """Smooth move from a to b centred on contact (fastest at C)."""
    return lambda t: a + (b - a) / (1 + np.exp(-(t - C) / (width / 4)))


def test_forehand_topspin_detected():
    tr = _track(lambda t: np.full_like(t, 0.62), _sweep(0.62, 0.42))  # bat side, rising
    key, f = strokes.detect(tr, "right", C)
    assert f["side_score"] > 0.15 and f["rise"] > 0.35
    assert key == "forehand_topspin"


def test_forehand_loop_vs_backspin_needs_a_low_start():
    tr = _track(lambda t: np.full_like(t, 0.62), _sweep(0.80, 0.40))  # starts well below the hips
    assert strokes.detect(tr, "right", C)[0] == "forehand_loop_backspin"


def test_backhand_push_and_chop():
    across_down = _track(lambda t: np.full_like(t, 0.46), _sweep(0.50, 0.58))
    assert strokes.detect(across_down, "right", C)[0] == "backhand_push"
    bat_side_big_down = _track(lambda t: np.full_like(t, 0.62), _sweep(0.30, 0.65))
    assert strokes.detect(bat_side_big_down, "right", C)[0] == "chop"


def test_forced_wing_overrides_side():
    tr = _track(lambda t: np.full_like(t, 0.62), _sweep(0.62, 0.42))
    assert strokes.detect(tr, "right", C, wing="backhand")[0].startswith("backhand")


def test_requested_wing_never_becomes_a_chop():
    # "Fix my backhand" rendered a Chop breakdown on the coach sample.
    bat_side_big_down = _track(lambda t: np.full_like(t, 0.62), _sweep(0.30, 0.65))
    assert strokes.detect(bat_side_big_down, "right", C, wing="backhand")[0] == "backhand_push"
    assert strokes.STROKE_TYPES[strokes.detect(bat_side_big_down, "right", C, wing="forehand")[0]].stroke == "forehand"


def test_key_moments_follow_the_swing_direction():
    down = _track(lambda t: np.full_like(t, 0.62), _sweep(0.30, 0.65))
    (prep, contact, fin), _ = key_moments(down, "right", direction="down")
    y = lambda tr, s: float(tr.lm[int(round(s * FPS)), 16, 1])
    assert prep < contact < fin
    assert y(down, prep) < y(down, fin)  # starts high (small y), finishes low
    up = _track(lambda t: np.full_like(t, 0.62), _sweep(0.62, 0.42))
    (prep, contact, fin), _ = key_moments(up, "right", direction="up")
    assert y(up, prep) > y(up, fin)


@pytest.mark.parametrize("key", list(strokes.STROKE_TYPES))
def test_every_stroke_type_has_a_template(key):
    st = strokes.STROKE_TYPES[key]
    b = OfflineAnalyzer().from_video("x.mp4", st.stroke, [], {}, [0.5, 1.0, 1.5], stroke_type=key)
    assert b.stroke_type == key and len(b.steps) == 3
    assert all(len(s.lines) == 2 and all(len(l) <= 45 for l in s.lines) for s in b.steps)


@pytest.mark.parametrize("text,key", [
    ("He chops from far back", "chop"),
    ("short backhand flick over the table", "backhand_flick"),
    ("backhand push, long and low", "backhand_push"),
    ("forehand loop against heavy backspin", "forehand_loop_backspin"),
    ("flat forehand drive", "forehand_drive"),
    ("forehand topspin from mid distance", "forehand_topspin"),
    ("pendulum serve with sidespin", "serve"),
    ("footwork drill", None),
])
def test_stroke_type_from_text(text, key):
    assert strokes.from_text(text) == key


def test_resolve():
    assert strokes.resolve("") is None and strokes.resolve("auto") is None
    assert strokes.resolve("Forehand topspin") == "forehand_topspin"
    with pytest.raises(ValueError):
        strokes.resolve("tomahawk")


def test_text_breakdown_auto_detects_type(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    res = run_text("Long pips player who chops everything", str(tmp_path), stroke="")
    b = json.loads((tmp_path / "breakdown.json").read_text())
    assert res["stroke_type"] == "chop" and res["stroke_type_detected"] == {"from": "text"}
    assert b["stroke"] == "chop" and b["headline"] == "High to low. Cut under it."


def test_claude_request_uses_structured_output_and_fallbacks():
    seen = {}
    reply = {"player": "Ma Long", "stroke": "forehand", "stroke_type": "forehand_topspin",
             "handedness": "right", "headline": "Low and through.", "grip": "g", "stance": "s",
             "swing_path": "p", "contact_point": "c", "follow_through": "f", "source": "x",
             "steps": [{"title": f"Step {i}", "lines": ["a", "b"], "highlight_words": [],
                        "key_time_s": None, "callouts": []} for i in range(3)]}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"], seen["body"], seen["beta"] = str(req.url), json.loads(req.content), req.headers.get("anthropic-beta")
        return httpx.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": json.dumps(reply)}], "stop_reason": "end_turn",
            "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}})

    import anthropic
    client = anthropic.Anthropic(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    b = ClaudeAnalyzer(model="claude-opus-5-5", client=client).from_text(
        "loops hard", "forehand", "Ma Long", stroke_type="forehand_topspin")
    body = seen["body"]
    assert "tool_choice" not in body and body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["beta"]
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "Forehand topspin" in body["messages"][0]["content"][0]["text"]
    assert b.stroke_type == "forehand_topspin" and b.source == "claude:claude-opus-5-5"


def test_blocks_can_be_picked_but_are_not_auto_detected():
    """1c: the block types exist for the Breakdown form and the coaching prompt; auto-detection
    never returns them (eval/train_wing.py block: not validated)."""
    from technique.analyze import _TEMPLATES
    for key, wing in (("backhand_block", "backhand"), ("forehand_block", "forehand")):
        st = strokes.STROKE_TYPES[key]
        assert strokes.resolve(key) == key and st.stroke == wing and "early" in st.focus
        assert len(_TEMPLATES[key]["steps"]) == 3
    for side_score in (-1.0, 1.0):
        for rise in (-0.5, 0.0, 0.5):
            for path in (0.3, 1.0, 2.0):
                assert "block" not in strokes.classify({"side_score": side_score, "rise": rise, "low_start": 0.0, "path": path})
