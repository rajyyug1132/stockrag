import tiktoken

from stockrag.ingestion.chunk import chunk_text

_ENCODING = tiktoken.get_encoding("cl100k_base")


def test_short_text_produces_one_chunk() -> None:
    chunks = chunk_text("Risk factors are important.", section="item_1a_risk_factors")
    assert len(chunks) == 1
    assert chunks[0].section == "item_1a_risk_factors"
    assert chunks[0].char_start == 0


def test_empty_text_produces_no_chunks() -> None:
    assert chunk_text("", section="other") == []


def test_long_text_overlaps_between_chunks() -> None:
    # ~2000 tokens of repeated words, well beyond the 20-token window below.
    text = " ".join(f"word{i}" for i in range(2000))
    chunks = chunk_text(text, section="item_7_mda", chunk_tokens=20, overlap_tokens=5)

    assert len(chunks) > 1
    # Consecutive chunks should share trailing/leading tokens (the overlap).
    # Compared at the token level since BPE doesn't split on word boundaries
    # (e.g. "word123" isn't one token).
    first_tokens = _ENCODING.encode(chunks[0].text)
    second_tokens = _ENCODING.encode(chunks[1].text)
    assert first_tokens[-5:] == second_tokens[:5]


def test_chunks_cover_full_text_without_gaps() -> None:
    text = " ".join(f"word{i}" for i in range(500))
    chunks = chunk_text(text, section="other", chunk_tokens=50, overlap_tokens=10)

    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == len(text)
    for prev, nxt in zip(chunks, chunks[1:]):
        assert nxt.char_start <= prev.char_end  # overlapping, no gap
