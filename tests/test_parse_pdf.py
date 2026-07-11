from stockrag.ingestion.parse import OTHER_SECTION
from stockrag.ingestion.parse_pdf import split_indian_sections


def test_headings_route_to_canonical_sections():
    text = "\n".join(
        [
            "Cover page boilerplate",
            "Management Discussion and Analysis",
            "Revenue grew 12% driven by the retail segment.",
            "Directors' Report",
            "The board recommends a dividend of Rs 5 per share.",
            "Risk Management",
            "Foreign exchange volatility is the principal risk.",
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
    text = "We describe our risk management framework below.\nContent."
    sections = split_indian_sections(text)
    assert len(sections) == 1
    assert sections[0].name == OTHER_SECTION


if __name__ == "__main__":
    test_headings_route_to_canonical_sections()
    test_sentence_lines_are_not_treated_as_headings()
    print("ok")
