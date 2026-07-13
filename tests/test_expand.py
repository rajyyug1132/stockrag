from stockrag.rag.expand import _stitch


def test_stitch_dedups_overlap():
    # chunk0 "ABCDEF" [0,6), chunk1 "EFGHIJ" [4,10) — 2-char overlap dropped.
    assert _stitch([(0, 6, "ABCDEF"), (4, 10, "EFGHIJ")]) == "ABCDEFGHIJ"


def test_stitch_adjacent_and_gap():
    assert _stitch([(0, 3, "ABC"), (3, 6, "DEF")]) == "ABCDEF"       # adjacent
    assert _stitch([(0, 3, "ABC"), (5, 8, "FGH")]) == "ABC\nFGH"     # gap -> newline


def test_stitch_single_and_nested():
    assert _stitch([(0, 3, "ABC")]) == "ABC"
    # second chunk fully inside the first -> nothing appended.
    assert _stitch([(0, 10, "ABCDEFGHIJ"), (2, 5, "CDE")]) == "ABCDEFGHIJ"


if __name__ == "__main__":
    test_stitch_dedups_overlap()
    test_stitch_adjacent_and_gap()
    test_stitch_single_and_nested()
    print("ok")
