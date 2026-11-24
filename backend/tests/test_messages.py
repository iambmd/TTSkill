"""Backend messages by key (messages.py): the same keys and English as frontend/messages/en.json,
a Vietnamese translation for each, and the references the page translates from."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app import jobs, main, pipelines
from messages import EN, Msg, say
from test_api import api, ran  # noqa: F401  (fixtures)

CATALOGS = Path(__file__).resolve().parents[2] / "frontend" / "messages"


def _lookup(tree: dict, key: str):
    for part in key.split("."):
        tree = tree[part]
    return tree


def _args(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)", text))


@pytest.mark.parametrize("lang", ["en", "vi"])
def test_every_backend_message_is_in_the_frontend_catalogue(lang):
    tree = json.loads((CATALOGS / f"{lang}.json").read_text())
    for key, english in EN.items():
        text = _lookup(tree, key)
        assert isinstance(text, str) and text.strip(), key
        if callable(english):
            continue
        assert _args(text) == _args(english), (lang, key)
        if lang == "en":
            assert text == english, key   # one English, so the page and the server never disagree


def test_a_message_renders_its_english_and_a_nested_reference():
    m = Msg("validation.tooLong", length="12:00", max=Msg("common.minutes", n=10))
    assert str(m) == "That video is 12:00 long. Uploads can be up to 10 minutes: trim it and try again."
    assert m.ref() == {"key": "validation.tooLong",
                       "args": {"length": "12:00", "max": {"key": "common.minutes", "args": {"n": 10}}}}
    assert str(Msg("common.minutes", n=1)) == "1 minute"
    with pytest.raises(KeyError):
        Msg("progress.nope")


def test_422s_carry_a_reference_the_page_can_translate(api, ran):
    r = api.post("/jobs/breakdown", data={"text": "x", "stroke": "lob"})
    assert r.status_code == 422 and r.json()["detail"] == "Unknown stroke: lob. Leave it blank to auto-detect."
    assert r.json()["detailRef"] == {"key": "validation.unknownStroke", "args": {"stroke": "lob"}}
    r = api.post("/jobs/breakdown", data={"text": "x", "hand": "both"})
    ref = r.json()["detailRef"]
    assert ref["key"] == "validation.choice" and ref["args"]["label"] == {"key": "validation.labels.hand", "args": {}}
    assert ref["args"]["options"]["key"] == "validation.or"
    r = api.post("/jobs/autocut", data={"url": "https://youtu.be/g3n9jVP0fMU", "top_n": "abc"})
    assert r.json()["detail"] == "Rallies in the reel must be a whole number."
    assert r.json()["detailRef"]["key"] == "validation.wholeNumber"
    r = api.post("/jobs/coach", data={"request": "fix", "url": "https://youtube.com/playlist?list=x"})
    assert r.json()["detailRef"]["key"] == "validation.playlist"


def test_new_text_without_a_reference_drops_the_old_one(api):
    job = jobs.create("breakdown", {})
    jobs.update(job["id"], **say("progress.breakdown.pose"))
    assert jobs.load(job["id"])["messageRef"]["key"] == "progress.breakdown.pose"
    jobs.update(job["id"], message="something new")
    assert jobs.load(job["id"])["messageRef"] is None   # the page shows "something new", not the stale key


def test_failures_carry_their_reference(api):
    from technique.errors import NoPlayer
    job = jobs.create("breakdown", {})
    jobs.fail(job["id"], NoPlayer(Msg("serverErrors.player.onlySeen", pct=31)))
    got = jobs.load(job["id"])
    assert got["failureHint"].startswith("We could only see the player in 31% of the clip.")
    assert got["failureRef"] == {"key": "serverErrors.player.onlySeen", "args": {"pct": 31}} == got["messageRef"]
    jobs.fail(job["id"], RuntimeError("boom"))
    got = jobs.load(job["id"])
    assert got["failureHint"] == jobs.FAILED and got["failureRef"]["key"] == "progress.failed" and "boom" not in str(got)


def test_breakdown_progress_shows_stages_not_log_lines(api):
    job = jobs.create("breakdown", {})
    report = pipelines._progress(job["id"])
    report("window 54.0-60.2s (rally)")
    got = jobs.load(job["id"])
    assert got["message"] == "Finding the stroke..." and got["messageRef"]["key"] == "progress.breakdown.finding"
    report("bat hand: right (paddle colour)")
    report("claude failed (timeout); using offline analyzer")   # a detail: the stage text stays
    got = jobs.load(job["id"])
    assert got["messageRef"]["key"] == "progress.breakdown.hand" and got["progress"] == 0.5


def test_few_rallies_warnings_are_keyed():
    assert pipelines.few_rallies_msg(0).key == "progress.autocut.heardNone"
    assert pipelines.few_rallies_msg(1).key == "progress.autocut.heardOne"
    assert pipelines.few_rallies_msg(2) is None
    assert str(Msg("progress.autocut.heardFew", n=3)).startswith("We only heard 3 rallies.")


def test_link_errors_carry_references():
    from app import download
    with pytest.raises(download.LinkError) as e:
        download.check_info({"duration": 600}, "breakdown")
    assert str(e.value) == "That video is 10:00 long. Use one under 3 minutes, or trim it and upload the file."
    assert e.value.ref["key"] == "serverErrors.link.tooLong" and e.value.ref["args"]["max"]["args"] == {"n": 3}
    assert download._friendly(RuntimeError("ERROR: Private video")).ref["key"] == "serverErrors.link.private"
