from app.cut import padded_segments


def test_pads_clamps_and_merges():
    segs = padded_segments([(1.0, 5.0), (6.0, 9.0), (20.0, 29.5)], total=30.0, pad=1.5)
    assert segs == [(0.0, 10.5), (18.5, 30.0)]


def test_highlights_keep_order_without_merging():
    segs = padded_segments([(20.0, 25.0), (1.0, 5.0)], total=30.0, pad=1.5, merge=False)
    assert segs == [(18.5, 26.5), (0.0, 6.5)]


def test_montage_padding_stops_at_clip_joins():
    segs = padded_segments([(1, 3.9), (4.1, 7)], total=10, merge=False,
                           bounds=[(0, 4), (4, 10)])
    assert segs == [(0, 4), (4, 8.5)]


def test_highlight_selection_keeps_clip_bounds_with_each_rally(monkeypatch):
    from pathlib import Path
    from app import pipelines
    from app.rally import Rally
    monkeypatch.setattr(pipelines, "duration", lambda _: 20)
    found = [Rally(1, 3.9, 4, clip_bounds=(0, 4)), Rally(4.1, 7, 9, clip_bounds=(4, 20))]
    rallies, segments = pipelines.pick_segments(found, Path("unused"), "highlights", 2)
    assert [r.hits for r in rallies] == [9, 4]
    assert segments == [(4, 8.5), (0, 4)]
