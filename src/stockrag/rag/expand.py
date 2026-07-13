"""Small-to-big retrieval: expand each reranked (small, precise) chunk to a
window of its neighbours in the same filing section (bigger, more context),
before handing text to the LLM. Citations still point at the retrieved chunk's
own metadata, so groundedness is unchanged — the LLM just sees more around it.

No re-ingestion needed: chunk metadata already carries section + char offsets,
so neighbours are reconstructed from the existing store.
"""

from collections import defaultdict

from langchain_core.documents import Document

from stockrag.rag.retrieve import _ticker_documents


def _stitch(chunks: list[tuple[int, int, str]]) -> str:
    """Concatenate section-chunks (sorted by char_start) into one string,
    dropping the char-level overlap between adjacent chunks."""
    start0, prev_end, text0 = chunks[0]
    out = text0
    for cs, ce, text in chunks[1:]:
        if cs >= prev_end:
            out += ("" if cs == prev_end else "\n") + text
        else:  # overlap: append only the tail past what we already have
            out += text[min(prev_end - cs, len(text)):]
        prev_end = max(prev_end, ce)
    return out


def expand_docs(docs: list[Document], ticker: str, window: int = 1) -> list[Document]:
    """Return docs with page_content widened to ±window sibling chunks from the
    same (accession, section). window=0 is a no-op. Metadata is preserved."""
    if window <= 0:
        return docs

    # (accession, section) -> chunks sorted by char_start.
    groups: dict[tuple, list[tuple[int, int, str]]] = defaultdict(list)
    for d in _ticker_documents(ticker):
        m = d.metadata
        groups[(m.get("accession"), m.get("section"))].append(
            (m.get("char_start", 0), m.get("char_end", 0), d.page_content)
        )
    for g in groups.values():
        g.sort()

    expanded: list[Document] = []
    for d in docs:
        m = d.metadata
        group = groups.get((m.get("accession"), m.get("section")))
        cs = m.get("char_start", 0)
        # locate this chunk in its section by char_start; widen by ±window.
        idx = next((i for i, c in enumerate(group or []) if c[0] == cs), None)
        if group is None or idx is None:
            expanded.append(d)  # ponytail: unmatched chunk falls back to itself
            continue
        lo = max(0, idx - window)
        hi = min(len(group), idx + window + 1)
        expanded.append(Document(page_content=_stitch(group[lo:hi]), metadata=m))
    return expanded


def demo() -> None:
    # Two overlapping chunks of the section text "ABCDEFGHIJ":
    #   chunk0 = "ABCDEF" [0,6), chunk1 = "EFGHIJ" [4,10) — 2-char overlap.
    assert _stitch([(0, 6, "ABCDEF"), (4, 10, "EFGHIJ")]) == "ABCDEFGHIJ"
    # Adjacent, no overlap.
    assert _stitch([(0, 3, "ABC"), (3, 6, "DEF")]) == "ABCDEF"
    # Gap between chunks → newline join.
    assert _stitch([(0, 3, "ABC"), (5, 8, "FGH")]) == "ABC\nFGH"
    # Single chunk unchanged.
    assert _stitch([(0, 3, "ABC")]) == "ABC"
    print("ok")


if __name__ == "__main__":
    demo()
