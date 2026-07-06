from stockrag.ingestion.parse import html_to_text, split_sections

SAMPLE_HTML = """
<html>
<head><style>.x { color: red; }</style></head>
<body>
<script>console.log("noise");</script>
<p>Cover page text before any item.</p>
<p>ITEM 1. BUSINESS</p>
<p>We build widgets and sell them worldwide.</p>
<p>ITEM 1A. RISK FACTORS</p>
<p>Our business faces competition and supply chain risk.</p>
<p>ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS</p>
<p>Revenue grew 10% year over year.</p>
</body>
</html>
"""


def test_html_to_text_strips_script_and_style() -> None:
    text = html_to_text(SAMPLE_HTML)
    assert "console.log" not in text
    assert "color: red" not in text
    assert "widgets" in text


def test_split_sections_buckets_by_item() -> None:
    text = html_to_text(SAMPLE_HTML)
    sections = split_sections(text)
    names = [s.name for s in sections]

    assert "item_1_business" in names
    assert "item_1a_risk_factors" in names
    assert "item_7_mda" in names

    business = next(s for s in sections if s.name == "item_1_business")
    assert "widgets" in business.text

    risk = next(s for s in sections if s.name == "item_1a_risk_factors")
    assert "competition" in risk.text

    mda = next(s for s in sections if s.name == "item_7_mda")
    assert "Revenue grew" in mda.text


def test_text_before_first_item_is_other() -> None:
    text = html_to_text(SAMPLE_HTML)
    sections = split_sections(text)
    other = next(s for s in sections if s.name == "other")
    assert "Cover page" in other.text
