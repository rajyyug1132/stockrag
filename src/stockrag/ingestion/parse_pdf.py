"""Parse Indian annual-report PDFs into sections, mirroring parse.py's contract.

Indian annual reports have no standardized "Item N" structure like SEC 10-Ks;
they carry recurring named sections (MD&A, Directors' Report, risk, etc.) whose
headings vary in casing and wording. We match those headings heuristically and
fall back to "other", exactly as the SEC splitter does.
"""

import re

from pypdf import PdfReader

from stockrag.ingestion.parse import OTHER_SECTION, Section

# Heading text (substring, case-insensitive) -> canonical section name. Order
# matters: first match on a heading-like line wins. Kept deliberately short —
# these are the sections useful for research Q&A over an annual report.
SECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"management\s+discussion\s+and\s+analysis", re.I), "mda"),
    (re.compile(r"\bdirectors?['’\s]*\s*report\b", re.I), "directors_report"),
    (re.compile(r"risk\s+management|risk\s+factors|principal\s+risks", re.I), "risk"),
    (re.compile(r"corporate\s+governance", re.I), "corporate_governance"),
    (re.compile(r"business\s+(overview|responsibility)|about\s+(us|the\s+company)", re.I), "business"),
    (re.compile(r"auditor'?s?\s+report|independent\s+auditor", re.I), "auditors_report"),
    (re.compile(r"notes\s+to\s+(the\s+)?(financial|accounts)", re.I), "notes"),
]

# A heading line is short and mostly non-sentence: annual-report section titles
# rarely exceed ~80 chars and don't end in a period.
_MAX_HEADING_LEN = 80


def pdf_to_text(path: str) -> str:
    reader = PdfReader(path)
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _match_heading(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADING_LEN or stripped.endswith("."):
        return None
    for pattern, name in SECTION_PATTERNS:
        if pattern.search(stripped):
            return name
    return None


# Sections shorter than this are TOC entries / page-header scraps, not content.
# Calibrated on RIL IAR 2024: real sections run 8k-30k chars, TOC scraps <600.
_MIN_SECTION_CHARS = 600


def split_indian_sections(text: str) -> list[Section]:
    current_name = OTHER_SECTION
    current_lines: list[str] = []
    raw: list[Section] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if body:
            raw.append(Section(name=current_name, text=body))

    for line in text.split("\n"):
        name = _match_heading(line)
        if name is not None:
            flush()
            current_name = name
            current_lines = []
        else:
            current_lines.append(line)
    flush()

    # Repeated page headers re-trigger the same section dozens of times in a
    # real annual report; coalesce adjacent same-name runs, then drop scraps.
    merged: list[Section] = []
    for section in raw:
        if merged and merged[-1].name == section.name:
            merged[-1] = Section(name=section.name, text=merged[-1].text + "\n" + section.text)
        else:
            merged.append(section)
    return [s for s in merged if len(s.text) >= _MIN_SECTION_CHARS]


def parse_pdf_sections(path: str) -> list[Section]:
    return split_indian_sections(pdf_to_text(path))
