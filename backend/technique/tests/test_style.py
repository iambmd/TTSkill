"""The style profile drives pacing, templates and the prompt, and none of the reference
channel's on-screen wording or series names end up in our output."""
import json
from pathlib import Path

import pytest

from technique import style
from technique.analyze import SYSTEM, _TEMPLATES, OfflineAnalyzer
from technique.render import layer_drill, layer_intro, layer_recap, layer_step

ROOT = Path(__file__).resolve().parents[2]
# Phrases seen in the reference videos. We describe their structure, never reuse their words.
REFERENCE_PHRASES = ["TIP DOWN", "BRUSH UP", "FLIP UP", "FOOT OUT", "KNEE BENT", "BODY TURNED",
                     "QUICK BREAKDOWN", "COPY THE PRO", "SPOT 3 DIFFERENCES", "SAME SECRET",
                     "START BELOW THE BALL", "SHADOW SWINGS IN A MIRROR"]


def test_profile_loads_with_measured_pacing():
    p = style.profile()
    assert p["structure"]["step_count"] == 3
    pace = style.pacing()
    assert 0.5 <= pace["freeze_s"] <= 3 and 0 < pace["slowmo_factor"] < 1
    assert len(style.phase_colours()) >= 3


def test_prompt_carries_the_style_guide():
    assert "Style guide" in SYSTEM and "2-word cue" in SYSTEM
    assert "practice drill" in SYSTEM


@pytest.mark.parametrize("key", sorted(_TEMPLATES))
def test_templates_follow_the_profile(key):
    t = _TEMPLATES[key]
    assert len(t["steps"]) == style.profile()["structure"]["step_count"]
    assert all(len(title.split()) == 2 for title, *_ in t["steps"])
    assert t["recap"] and t["drill"]


def test_no_reference_wording_in_our_output():
    texts = [json.dumps(_TEMPLATES), (ROOT / "style" / "swift_style.json").read_text(),
             (ROOT / "technique" / "render.py").read_text()]
    blob = " ".join(texts).upper()
    for phrase in REFERENCE_PHRASES:
        assert phrase not in blob, phrase


def test_cards_render():
    b = OfflineAnalyzer().from_text("loops", "forehand", "Ma Long", stroke_type="forehand_topspin")
    for layer in (layer_intro(b), layer_step(b, 1, paused=True), layer_recap(b), layer_drill(b)):
        assert layer.shape == (1920, 1080, 4) and layer[:, :, 3].any()
