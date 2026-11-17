from pathlib import Path

import pytest

from app.rally import detect_rallies

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "IMG_8782.MOV"


@pytest.mark.skipif(not SAMPLE.exists(), reason="put IMG_8782.MOV in samples/")
def test_finds_longest_rally(tmp_path):
    rallies = detect_rallies(SAMPLE, tmp_path, threshold=3.0)
    assert any(r.start < 66 and r.end > 54 for r in rallies)


def test_weak_chain_cannot_bridge_real_break_or_extend_prep():
    import numpy as np
    from app.rally import group_rallies_anchored
    times = np.array([0., .3, .6, 1., 1.3, 1.6, 2., 2.3, 2.6, 3., 3.3, 3.6])
    ratios = np.array([2., 2., 2., 4., 2., 4., 2., 2., 2., 4., 2., 4.])
    rs = group_rallies_anchored(times, ratios, gap=1.0, min_hits=3)
    assert len(rs) == 2
    assert rs[0].end < rs[1].start
    assert rs[0].start >= .5  # prep chain does not pull the start to zero


def test_only_weak_bounces_never_start_a_rally():
    import numpy as np
    from app.rally import group_rallies_anchored
    assert not group_rallies_anchored(np.arange(10) * .4, np.full(10, 2.1))


def test_soft_in_rally_onsets_are_kept():
    import numpy as np
    from app.rally import group_rallies_anchored
    rs = group_rallies_anchored(np.array([0., .4, .8, 1.2]), np.array([4., 2., 2., 4.]))
    assert len(rs) == 1 and rs[0].hits == 4


def test_shared_audio_timestamps_use_actual_sample_hop(tmp_path):
    import numpy as np
    from scipy.io import wavfile
    from app.rally import detect_hits
    from technique.audio import detect_hits as technique_hits
    sr = 22050
    x = np.zeros(sr * 120, np.int16)
    pulse = (np.sin(2 * np.pi * 3000 * np.arange(220) / sr) * 20000).astype(np.int16)
    x[119 * sr:119 * sr + len(pulse)] = pulse
    wavfile.write(tmp_path / 'audio.wav', sr, x)
    hits = detect_hits(tmp_path / 'audio.wav')
    assert abs(hits[-1] - 119) < .03
    np.testing.assert_array_equal(hits, technique_hits(x.astype(np.float32) / 32768, sr))
