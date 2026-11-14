from pathlib import Path

import pytest

from app.rally import detect_rallies

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "IMG_8782.MOV"


@pytest.mark.skipif(not SAMPLE.exists(), reason="put IMG_8782.MOV in samples/")
def test_finds_longest_rally(tmp_path):
    rallies = detect_rallies(SAMPLE, tmp_path, threshold=3.0)
    assert any(r.start < 66 and r.end > 54 for r in rallies)
