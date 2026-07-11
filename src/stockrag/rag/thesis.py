"""Thesis briefing: factor engine + RAG evidence synthesized into one document.

Ports the structured-thesis pattern (summary / bull / bear / risks, every
point evidence-cited) into StockRAG: quantitative side from the XBRL factor
report, qualitative side from citation-enforced RAG answers over filings.
"""

from dataclasses import dataclass

import yaml

from stockrag.config import settings
from stockrag.factor_engine.report import FactorReport, build_factor_report
from stockrag.rag.answer import AnswerResult, ask
from stockrag.rag.llm import get_llm
from stockrag.rag.metrics import citation_coverage

PROMPT_VERSION = "thesis_v1"

THESIS_QUESTIONS: list[tuple[str, str]] = [
    ("risks", "What are the most significant risk factors the company discloses?"),
    ("competition", "What is the company's competitive position and how does it differentiate?"),
    (
        "capital_allocation",
        "How does the company generate and allocate capital (cash flow, buybacks, dividends, R&D, acquisitions)?",
    ),
]


@dataclass(frozen=True)
class ThesisSection:
    topic: str
    question: str
    result: AnswerResult
    grounding: float  # fraction of substantive sentences carrying a citation


@dataclass(frozen=True)
class ThesisResult:
    ticker: str
    factors: FactorReport
    sections: list[ThesisSection]
    synthesis: str
    prompt_version: str


def build_thesis(ticker: str, llm_provider: str | None = None) -> ThesisResult:
    ticker = ticker.upper()
    factors = build_factor_report(ticker)

    sections = []
    for topic, question in THESIS_QUESTIONS:
        result = ask(question, ticker, llm_provider=llm_provider)
        sections.append(
            ThesisSection(
                topic=topic,
                question=question,
                result=result,
                grounding=citation_coverage(result.answer),
            )
        )

    data = yaml.safe_load(
        (settings.prompts_dir / f"{PROMPT_VERSION}.yaml").read_text(encoding="utf-8")
    )
    evidence = "\n\n".join(f"## {s.topic}\n{s.result.answer}" for s in sections)
    synthesis = get_llm(llm_provider).invoke(
        [
            ("system", data["synthesis_system"]),
            (
                "human",
                data["synthesis_user"].format(
                    ticker=ticker,
                    factors=factors.model_dump_json(indent=2),
                    evidence=evidence,
                ),
            ),
        ]
    )

    return ThesisResult(
        ticker=ticker,
        factors=factors,
        sections=sections,
        synthesis=str(synthesis.content),
        prompt_version=PROMPT_VERSION,
    )
