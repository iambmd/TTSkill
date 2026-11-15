from app.cut import padded_segments


def test_pads_clamps_and_merges():
    segs = padded_segments([(1.0, 5.0), (6.0, 9.0), (20.0, 29.5)], total=30.0, pad=1.5)
    assert segs == [(0.0, 10.5), (18.5, 30.0)]


def test_highlights_keep_order_without_merging():
    segs = padded_segments([(20.0, 25.0), (1.0, 5.0)], total=30.0, pad=1.5, merge=False)
    assert segs == [(18.5, 26.5), (0.0, 6.5)]
