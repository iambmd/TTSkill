"""Pure-function tests for the eval harness metrics."""
from __future__ import annotations

from eval.metrics import in_spans, iou, match_rallies, onset_play_split


def test_iou():
    assert iou((0, 10), (0, 10)) == 1.0
    assert iou((0, 10), (10, 20)) == 0.0
    assert abs(iou((0, 10), (5, 15)) - 1 / 3) < 1e-9


def test_match_perfect():
    r = match_rallies([(0, 10), (20, 30)], [(0, 10), (20, 30)])
    assert r["precision"] == 1.0 and r["recall"] == 1.0
    assert r["merges"] == 0 and r["splits"] == 0 and r["false_rallies"] == 0


def test_match_merge():
    # One detection swallowing two true rallies: a merge, and no IoU-0.5 match.
    r = match_rallies([(0, 30)], [(0, 10), (20, 30)])
    assert r["merges"] == 1
    assert r["matched"] == 0


def test_match_split():
    r = match_rallies([(0, 4), (6, 10)], [(0, 10)])
    assert r["splits"] == 1


def test_false_rally():
    # A detection entirely in dead time barely touches real play.
    r = match_rallies([(50, 60)], [(0, 10)])
    assert r["false_rallies"] == 1
    assert r["precision"] == 0.0


def test_onset_split():
    res = onset_play_split([1.0, 5.0, 99.0], play=[(0, 10)], prep=[(90, 95)], margin=0.0)
    assert res["in_play"] == 2 and res["in_dead"] == 1
    assert res["play_precision"] == round(2 / 3, 3)
    assert in_spans(10.2, [(0, 10)], margin=0.3)


def test_evaluations_have_isolated_workdirs(tmp_path, monkeypatch):
    from eval import run
    paths = []
    def evaluate(gt, workdir, use_pose, **kwargs):
        paths.append(workdir)
        (workdir / 'audio.wav').write_text(gt['name'])
        return {'ok': True}
    monkeypatch.setattr(run, '_evaluate', evaluate)
    for _ in range(2):
        assert run.evaluate({'name': 'same_clip'}, tmp_path, False) == {'ok': True}
    assert paths[0] != paths[1]
    assert all(not p.exists() for p in paths)
