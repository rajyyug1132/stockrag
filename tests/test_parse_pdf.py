from stockrag.ingestion.parse import OTHER_SECTION
from stockrag.ingestion.parse_pdf import _MIN_SECTION_CHARS, split_indian_sections

# Real sections are thousands of chars; pad fixture bodies past the
# TOC-scrap filter so the tests exercise routing, not the length cutoff.
PAD = "x" * _MIN_SECTION_CHARS


def test_headings_route_to_canonical_sections():
    text = "\n".join(
        [
            "Cover page boilerplate " + PAD,
            "Management Discussion and Analysis",
            "Revenue grew 12% driven by the retail segment. " + PAD,
            "Directors' Report",
            "The board recommends a dividend of Rs 5 per share. " + PAD,
            "Risk Management",
            "Foreign exchange volatility is the principal risk. " + PAD,
        ]
    )
    by_name = {s.name: s.text for s in split_indian_sections(text)}

    assert by_name[OTHER_SECTION].startswith("Cover page")
    assert "retail segment" in by_name["mda"]
    assert "dividend" in by_name["directors_report"]
    assert "Foreign exchange" in by_name["risk"]


def test_sentence_lines_are_not_treated_as_headings():
    # A line mentioning a section keyword but ending in a period (a real
    # sentence) must not split — only short heading-like lines do.
    text = "We describe our risk management framework below.\nContent. " + PAD
    sections = split_indian_sections(text)
    assert len(sections) == 1
    assert sections[0].name == OTHER_SECTION


def test_page_header_repeats_coalesce_and_toc_scraps_drop():
    # Page headers re-trigger the same section; adjacent runs must merge.
    # Tiny TOC fragments must be dropped entirely.
    text = "\n".join(
        [
            "Risk Management",
            "First risk page. " + PAD,
            "Risk Management",  # repeated page header
            "Second risk page. " + PAD,
            "Corporate Governance",
            "toc scrap",  # far below _MIN_SECTION_CHARS -> dropped
        ]
    )
    sections = split_indian_sections(text)
    assert [s.name for s in sections] == ["risk"]
    assert "First risk page" in sections[0].text and "Second risk page" in sections[0].text


if __name__ == "__main__":
    test_headings_route_to_canonical_sections()
    test_sentence_lines_are_not_treated_as_headings()
    test_page_header_repeats_coalesce_and_toc_scraps_drop()
    print("ok")
