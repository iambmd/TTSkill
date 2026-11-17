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


def test_player_audit_counts_wrong_identity_and_abstention_separately():
    import numpy as np
    from eval.audit_player import audit
    from technique.pose import PoseTrack
    lm = np.full((3,33,4), .8)
    lm[0,:,0] = .2
    lm[2] = np.nan
    tr = PoseTrack(1,100,100,np.arange(3),lm,np.zeros((3,33,3)))
    labels = {'frames': [{'time': i, 'box': [0,0,.5,1]} for i in range(3)]}
    result = audit(tr, labels)
    assert (result['correct'], result['wrong'], result['abstained']) == (1,1,1)


def test_baseline_loads_its_own_files_and_sibling_imports(monkeypatch):
    import subprocess
    import sys
    from pathlib import Path
    from eval.run import baseline_modules

    sources = {
        "rally": "from pathlib import Path\nVALUE = 17\nHERE = Path(__file__).parent\n",
        "floor_bounce": "from . import rally, clips\nVALUE = rally.VALUE + clips.VALUE\n",
        "clips": "from .rally import VALUE\n",
    }
    def git_show(cmd, **kwargs):
        name = Path(cmd[-1]).stem
        return subprocess.CompletedProcess(cmd, 0, sources[name], "")
    monkeypatch.setattr(subprocess, "run", git_show)
    with baseline_modules("test-revision") as (rally, floor):
        assert floor.VALUE == 34
        assert rally.HERE.is_dir()
        name, folder = rally.__package__, rally.HERE
        assert floor.rally is rally
    assert not folder.exists()
    assert not any(k == name or k.startswith(name + ".") for k in sys.modules)


def test_label_alias_keeps_the_same_label_file(tmp_path, monkeypatch):
    import json
    from eval import run
    (tmp_path / "low.mp4").touch()
    (tmp_path / "high.mp4").touch()
    label = tmp_path / "same.json"
    label.write_text(json.dumps({"video": "low.mp4", "also": ["high.mp4"], "rallies": []}))
    monkeypatch.setattr(run, "LABELS", tmp_path)
    monkeypatch.setattr(run, "SAMPLES", tmp_path)
    low, high = run.load_labels()
    assert low["labels"] == high["labels"] == label
    assert low["name"] == "same" and high["name"] == "same@high"
