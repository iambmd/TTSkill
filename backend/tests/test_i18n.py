"""A job's language (`lang`: en or vi): checked by the API, passed to the pipelines, and used by
the Claude prompts, the offline templates, the video prompt, the video labels and Coach's plan."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import i18n
from app import jobs, main
from technique.analyze import TEMPLATES, ClaudeAnalyzer, OfflineAnalyzer
from technique.schema import StrokeBreakdown

from test_api import api, ran  # noqa: F401  (fixtures)


def _error(r) -> str:
    return r.json()["detail"]


# ---------------------------------------------------------------- API

def test_breakdown_and_coach_take_a_language(api, ran, upload):
    r = api.post("/jobs/breakdown", data={"text": "loops", "lang": "vi"})
    assert r.status_code == 201 and r.json()["params"]["lang"] == "vi"
    assert ran["run_breakdown"][-1][-1] == {"lang": "vi"}
    r = api.post("/jobs/coach", files=upload(), data={"request": "sửa cú thuận tay", "lang": "vi"})
    assert r.status_code == 201 and r.json()["params"]["lang"] == "vi"
    assert ran["run_coach"][-1][-1] == {"lang": "vi"}


def test_english_is_the_default_and_adds_no_argument(api, ran, upload):
    r = api.post("/jobs/breakdown", data={"text": "loops"})
    assert r.json()["params"]["lang"] == "en" and not isinstance(ran["run_breakdown"][-1][-1], dict)
    api.post("/jobs/coach", files=upload(), data={"request": "fix my forehand", "lang": "en"})
    assert not isinstance(ran["run_coach"][-1][-1], dict)


@pytest.mark.parametrize("path", ["/jobs/breakdown", "/jobs/coach"])
def test_an_unknown_language_is_refused_like_the_frontend(api, ran, path):
    r = api.post(path, data={"text": "loops", "request": "fix", "lang": "fr"})
    assert r.status_code == 422 and _error(r) == "Language must be en or vi."


def test_change_player_keeps_the_language(api, ran, upload):
    first = api.post("/jobs/breakdown", files=upload(), data={"lang": "vi"}).json()
    again = api.post(f"/jobs/{first['id']}/rerun", data={"player_time": "1", "player_box": "0.1,0.1,0.5,0.9"})
    assert again.status_code == 201 and again.json()["params"]["lang"] == "vi"
    assert ran["run_breakdown"][-1][-1] == {"lang": "vi"}


# ---------------------------------------------------------------- Claude prompts

def test_the_language_rule_goes_after_the_cached_prompt():
    assert i18n.instruction("en") == "" and i18n.instruction(None) == ""
    rule = i18n.instruction("vi")
    for term in ("thuận tay", "trái tay", "mặt vợt", "cốt vợt", "giật", "giao bóng", "pha bóng"):
        assert term in rule
    from agent import brief
    sent = {}
    msg = SimpleNamespace(stop_reason="end_turn", parsed_output=object(), model="m",
                          usage=SimpleNamespace(input_tokens=1, output_tokens=1, cache_creation_input_tokens=0,
                                                cache_read_input_tokens=0))
    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(parse=lambda **kw: sent.update(kw) or msg)))
    brief.write("sửa cú thuận tay", {}, [], client=client, lang="vi")
    assert sent["system"] == brief.system_blocks()   # unchanged, so the cache still serves it
    assert "Vietnamese" in sent["messages"][0]["content"][0]["text"]
    brief.write("fix", {}, [], client=client)
    assert "Vietnamese" not in sent["messages"][0]["content"][0]["text"]


def test_the_vision_analyzer_asks_for_the_language():
    sent = {}
    out = StrokeBreakdown(stroke="forehand", headline="h", grip="g", stance="s", swing_path="p",
                          contact_point="c", follow_through="f", steps=[])
    msg = SimpleNamespace(stop_reason="end_turn", parsed_output=out, model="m",
                          usage=SimpleNamespace(input_tokens=1, output_tokens=1, cache_creation_input_tokens=0,
                                                cache_read_input_tokens=0))
    a = ClaudeAnalyzer.__new__(ClaudeAnalyzer)
    a.model, a.client = "m", SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(
        parse=lambda **kw: sent.update(kw) or msg)))
    a.from_text("loops", "forehand", lang="vi")
    assert "Vietnamese" in sent["messages"][0]["content"][-1]["text"]
    a.from_text("loops", "forehand")
    assert all("Vietnamese" not in c.get("text", "") for c in sent["messages"][0]["content"])


# ---------------------------------------------------------------- offline text

def test_every_template_exists_in_vietnamese_with_its_highlights_in_the_lines():
    assert set(TEMPLATES["vi"]) == set(TEMPLATES["en"])
    for lang, templates in TEMPLATES.items():
        for key, tpl in templates.items():
            assert len(tpl["steps"]) == 3, (lang, key)
            for title, lines, highlights, callouts in tpl["steps"]:
                assert len(lines) == 2 and all(len(x) <= 45 for x in lines), (lang, key, lines)
                assert all(any(w in x for x in lines) for w in highlights), (lang, key, highlights)
                assert all(c == c.upper() for c in callouts), (lang, key, callouts)


def test_the_offline_analyzer_writes_vietnamese():
    metrics = {"knee_angle_deg": 150, "stance_width_x_shoulders": 1.2, "elbow_angle_deg": 120,
               "wrist_height_hip0_shoulder1": 0.5}
    b = OfflineAnalyzer().from_video("clip", "forehand", [], {}, [0.5, 1.0, 1.5],
                                     contact_metrics=metrics, stroke_type="forehand_topspin", lang="vi")
    assert b.steps[0].title == "Hạ thấp" and b.drill.startswith("Vung tay không")
    assert b.stance == "Chân rộng bằng vai, khuỵu gối vừa phải (gối ~150°)."
    assert b.contact_point == "Chạm bóng giữa eo và ngực, phía trước người, khuỷu tay mở ~120°."
    en = OfflineAnalyzer().from_video("clip", "forehand", [], {}, [0.5, 1.0, 1.5],
                                      contact_metrics=metrics, stroke_type="forehand_topspin")
    assert en.stance == "Shoulder-width base with moderate knee bend (knees ~150 deg)."
    assert OfflineAnalyzer().from_text("x", "backhand", lang="vi").steps[0].title == "Khuỷu trước"


def test_the_video_prompt_is_written_in_the_language():
    from technique.video_prompt import build_prompts
    b = OfflineAnalyzer().from_text("x", "forehand", stroke_type="forehand_topspin", lang="vi")
    b.handedness = "right"
    vi = build_prompts(b, lang="vi")
    assert vi["prompt"].startswith("một người chơi bóng bàn tay phải thực hiện cú giật thuận tay.")
    assert "khoảnh khắc: hạ thấp" in vi["shots"][0]["prompt"] and vi["negative_prompt"] == build_prompts(b)["negative_prompt"]
    assert build_prompts(b)["prompt"].startswith("a right-handed table tennis player performs a forehand topspin.")


def test_the_video_labels_follow_the_language():
    from technique import render
    b = OfflineAnalyzer().from_text("x", "forehand", stroke_type="forehand_topspin", lang="vi")
    seen = []
    real = render.ImageDraw.ImageDraw.text
    def text(self, xy, t, *a, **k):
        seen.append(t)
        return real(self, xy, t, *a, **k)
    render.ImageDraw.ImageDraw.text = text
    try:
        render.layer_intro(b, "vi"), render.layer_step(b, 0, paused=True, lang="vi"), render.layer_drill(b, "vi")
    finally:
        render.ImageDraw.ImageDraw.text = real
    assert {"GIẬT THUẬN TAY", " ĐIỂM CẦN HỌC", "TẠM DỪNG", "THỬ BÀI TẬP"} <= set(seen)
    assert "HẠ THẤP" in seen and "PAUSED" not in seen


# ---------------------------------------------------------------- Coach

def test_coach_notes_label_the_fix_and_drill_in_the_language():
    from agent import notes
    got = notes.build("Chân bạn hơi thẳng.", fix="Khuỵu gối", drill="Vung tay không 20 lần.", lang="vi")
    assert "**Lỗi cần sửa nhất:** Khuỵu gối" in got["markdown"] and "**Bài tập:** Vung tay không" in got["markdown"]
    assert notes.build("1. Fix it.\n\n**Bài tập:** Gò 30 quả.")["drill"] == "Gò 30 quả."
    assert "**Drill:** Shadow 20." in notes.build("Bend more.", drill="Shadow 20.")["markdown"]


def test_the_offline_coaching_summary_is_vietnamese(monkeypatch):
    from agent import fixed
    b = OfflineAnalyzer().from_text("x", "forehand", stroke_type="forehand_topspin", lang="vi")
    monkeypatch.setattr("technique.analyze.OfflineAnalyzer.from_video", lambda self, *a, **k: b)
    facts = {"stroke": "forehand", "stroke_type": "forehand_topspin", "stroke_label": "Forehand topspin",
             "key_times_s": [1, 2, 3], "at_contact": {"elbow_angle_deg": 128, "knee_angle_deg": 150},
             "closest_pros": [{"name": "Ma Long", "score": 84}]}
    out = fixed.offline_report(facts, Path("clip"), None, "vi")
    assert out.summary.startswith("Cú giật thuận tay của bạn, đo lúc tiếp xúc bóng: khuỷu tay khoảng 128°, "
                                  "đầu gối khoảng 150°. Bạn giống Ma Long nhất (84% vóc dáng).")
    assert "**Cần tập trước tiên:**" in out.summary and "**Bài tập:**" in out.summary


def test_coach_titles_and_plan_in_vietnamese():
    from agent.tools import breakdown_title
    assert breakdown_title("forehand_topspin", "en") == "Forehand topspin breakdown"
    assert breakdown_title("forehand_topspin", "vi") == "Phân tích giật thuận tay"
    assert i18n.t("vi", "todo.pose", noun=i18n.t("vi", "noun.forehand")) == "Theo dõi bạn ở các cú thuận tay"
    assert i18n.t("en", "todo.pose", noun="forehand") == "Track you at your forehands"
    assert set(i18n._TEXT["vi"]) == set(i18n._TEXT["en"])
    assert i18n.norm("fr") == "en"
