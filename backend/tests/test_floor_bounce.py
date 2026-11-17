from pathlib import Path

import numpy as np
import pytest

from app.floor_bounce import crouch_fraction, is_crouched


def pose(shoulder: float, hip: float, ankle: float, wrist: float) -> np.ndarray:
    lm = np.full((33, 2), 0.5)
    lm[[11, 12], 1] = shoulder
    lm[[23, 24], 1] = hip
    lm[[27, 28], 1] = ankle
    lm[[15, 16], 1] = wrist
    return lm


STANDING = pose(shoulder=0.35, hip=0.52, ankle=0.75, wrist=0.45)   # ready position, bat up
BOUNCING = pose(shoulder=0.44, hip=0.53, ankle=0.75, wrist=0.61)   # bent over, hand near the floor


def test_bent_over_with_low_hand_is_crouched():
    assert is_crouched(BOUNCING)
    assert not is_crouched(STANDING)


def test_low_hand_while_upright_is_not_crouched():
    # e.g. a low backhand push: hand below the hip but torso up
    assert not is_crouched(pose(shoulder=0.35, hip=0.52, ankle=0.75, wrist=0.6))


def test_crouch_fraction_counts_frames_with_anyone_crouched():
    frames = [[STANDING, BOUNCING], [STANDING], [], [BOUNCING]]
    assert crouch_fraction(frames) == 0.5
    assert crouch_fraction([]) == 0.0


SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "IMG_8782.MOV"


@pytest.mark.skipif(not SAMPLE.exists(), reason="put IMG_8782.MOV in samples/")
def test_drops_pre_serve_floor_bounce_on_sample(tmp_path):
    from app.floor_bounce import drop_floor_bounces
    from app.rally import detect_rallies

    kept, dropped = drop_floor_bounces(SAMPLE, detect_rallies(SAMPLE, tmp_path))
    assert any(r.start < 17 and r.end > 15 for r in dropped)  # Duke bouncing the ball at ~14-16 s
    assert any(r.start < 66 and r.end > 54 for r in kept)     # the longest rally survives


def test_walking_and_discontinuities_do_not_count_as_swings():
    from app.floor_bounce import swing_fraction
    assert swing_fraction([[STANDING], [STANDING + [.08, 0]]]) == 0
    assert swing_fraction([[STANDING], [STANDING + [.5, 0]]]) == 0
    assert swing_fraction([[STANDING], [], [STANDING]]) == 0
    swinging = STANDING.copy()
    swinging[16, 0] += .1
    assert swing_fraction([[STANDING], [swinging]]) == 1


def test_missing_model_keeps_candidates(monkeypatch):
    from app import floor_bounce
    from technique import pose as pose_module
    from app.rally import Rally
    def missing():
        raise OSError('model unavailable')
    monkeypatch.setattr(pose_module, 'model_path', missing)
    rs = [Rally(1, 4, 6)]
    assert floor_bounce.drop_non_play(Path('unused.mp4'), rs) == (rs, [])


def test_background_players_and_pre_serve_bounces_are_rejected():
    from app.floor_bounce import shows_play
    swing = STANDING.copy()
    swing[16, 0] += .1
    assert shows_play([[STANDING], [swing], [STANDING], [swing]])
    assert not shows_play([[p * .1 for p in frame] for frame in [[STANDING], [swing]]])
    assert not shows_play([[BOUNCING], [BOUNCING], [BOUNCING], [STANDING]])
    assert not shows_play([[], []])


REGRESSION = Path(__file__).resolve().parents[1] / "eval" / "regressions" / "img8782_autocut.json"


@pytest.mark.skipif(not SAMPLE.exists(), reason="put IMG_8782.MOV in samples/")
def test_wide_shot_keeps_real_rallies_and_drops_non_play(tmp_path):
    """A far phone camera sees the near player from behind; real rallies must survive."""
    import json
    from app.floor_bounce import drop_non_play
    from app.rally import detect_rallies
    from eval.metrics import overlap

    labels = json.loads(REGRESSION.read_text())
    kept, _ = drop_non_play(SAMPLE, detect_rallies(SAMPLE, tmp_path))
    spans = [(r.start, r.end) for r in kept]
    missed = [p for p in labels["play"]
              if not any(overlap(k, (p["start"], p["end"])) > .5 * (p["end"] - p["start"]) for k in spans)]
    wrong = [n for n in labels["not_play"]
             if any(overlap(k, (n["start"], n["end"])) > .5 * (k[1] - k[0]) for k in spans)]
    assert not missed and not wrong, (missed, wrong)


def test_dropped_spans_say_why():
    from app.floor_bounce import why_not_play
    swing = STANDING.copy()
    swing[16, 0] += .1
    assert why_not_play([[STANDING], [swing], [STANDING], [swing]]) == ""
    assert why_not_play([[], []]) == "no player in view"
    assert why_not_play([[BOUNCING], [BOUNCING], [BOUNCING], [STANDING]]) == "bouncing the ball before a serve"
    assert why_not_play([[STANDING], [STANDING], [STANDING]]) == "nobody swinging"


def test_small_figures_in_one_clip_are_another_court():
    from app.floor_bounce import figure_size, other_court
    # coach_demo: this table's player ~.17-.18, the neighbouring court at the end ~.11-.13
    assert other_court([.155, .172, .18, .175, .13, .113, .12, .178, .182]) == [False] * 4 + [True] * 3 + [False] * 2
    assert other_court([.2]) == [False] and other_court([]) == []
    assert round(figure_size([[STANDING], [STANDING * .5, STANDING], []]), 3) == .17


def test_quiet_gap_between_merged_candidates_is_not_a_fast_swing():
    from app.floor_bounce import swing_fraction
    swing = STANDING.copy()
    swing[16, 0] += .1
    assert swing_fraction([[STANDING], [swing]], times=np.array([1.0, 3.5])) == 0
    assert swing_fraction([[STANDING], [swing]], times=np.array([1.0, 1.1])) == 1


def test_every_long_gap_is_scanned_for_joins():
    # Montage: 125.4-127.4 then 131.4-133.3 s, a 4.0 s gap with a crossfade at 129.2 s that the
    # old "gap <= MERGE_GAP" rule skipped; short gaps are already covered by the join margins.
    from app.floor_bounce import JOIN_MARGIN, gaps_to_scan
    from app.rally import Rally
    rallies = [Rally(107.0, 112.2, 13), Rally(119.7, 123.7, 10), Rally(125.4, 127.4, 4),
               Rally(131.4, 133.3, 5), Rally(133.4, 135.0, 4)]
    assert gaps_to_scan(rallies) == [(112.2, 119.7), (123.7, 125.4), (127.4, 131.4)]
    assert all(b - a > 2 * JOIN_MARGIN for a, b in gaps_to_scan(rallies))


def test_gap_chunks_overlap_by_one_crossfade_window():
    from app.floor_bounce import chunks
    assert chunks(0, 10) == [(0, 10)]
    parts = chunks(100.0, 145.0)
    assert parts[0][0] == 100.0 and parts[-1][1] == 145.0
    assert all(b[0] < a[1] for a, b in zip(parts, parts[1:]))   # overlapping, no hole
    assert all(b - a <= 20.0 for a, b in parts)
