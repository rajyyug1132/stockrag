import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

# Best-effort section splitter for the handful of Items most useful for
# research Q&A. Matches ANY "Item N" header (1-16, optional A/B suffix) so
# that untracked items (4, 8, 9, ...) still reset the current section to
# "other" instead of letting their content bleed into the last tracked
# section. TOC entries and inline-XBRL noise will also match; we don't try
# to filter those out precisely, we just accept "other" and duplicate
# section headers as the cost of staying simple.
ITEM_HEADER_RE = re.compile(r"^\s*ITEM\s+(\d{1,2}[AB]?)\b", re.IGNORECASE)

SECTION_NAMES = {
    "1": "item_1_business",
    "1A": "item_1a_risk_factors",
    "2": "item_2_properties",
    "3": "item_3_legal_proceedings",
    "7": "item_7_mda",
    "7A": "item_7a_market_risk",
}

OTHER_SECTION = "other"


@dataclass(frozen=True)
class Section:
    name: str
    text: str


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text("\n")


def split_sections(text: str) -> list[Section]:
    current_name = OTHER_SECTION
    current_lines: list[str] = []
    sections: list[Section] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append(Section(name=current_name, text=body))

    for line in text.split("\n"):
        match = ITEM_HEADER_RE.match(line.strip())
        if match:
            flush()
            current_name = SECTION_NAMES.get(match.group(1).upper(), OTHER_SECTION)
            current_lines = []
        else:
            current_lines.append(line)
    flush()

    return sections


def parse_filing_sections(html: str) -> list[Section]:
    return split_sections(html_to_text(html))
