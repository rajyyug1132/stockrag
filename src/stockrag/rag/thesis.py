"""Thesis briefing: factor engine + RAG evidence synthesized into one document.

Ports the structured-thesis pattern (summary / bull / bear / risks, every
point evidence-cited) into StockRAG: quantitative side from the XBRL factor
report, qualitative side from citation-enforced RAG answers over filings.
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass

import yaml

from stockrag.config import settings
from stockrag.factor_engine.report import FactorReport, build_factor_report
from stockrag.rag.answer import AnswerResult, Source, ask
from stockrag.rag.llm import get_llm
from stockrag.rag.metrics import citation_coverage, record_request
from stockrag.rag.store import get_vector_store

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


def _corpus_fingerprint(ticker: str) -> str:
    """Hash of the ticker's ingested accessions — cache validity key.
    # ponytail: pulls all chunk metadatas for the ticker; paginate if a
    # ticker ever holds >100k chunks."""
    got = get_vector_store()._collection.get(where={"ticker": ticker}, include=["metadatas"])
    accessions = sorted({m["accession"] for m in got["metadatas"]})
    return hashlib.sha256("|".join(accessions).encode()).hexdigest()[:16]


def _cache_path(ticker: str):
    return settings.data_dir / "thesis" / f"{ticker}.json"


def _load_cached(ticker: str, fingerprint: str) -> ThesisResult | None:
    path = _cache_path(ticker)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("fingerprint") != fingerprint or data.get("prompt_version") != PROMPT_VERSION:
        return None
    return ThesisResult(
        ticker=data["ticker"],
        factors=FactorReport(**data["factors"]),
        sections=[
            ThesisSection(
                topic=s["topic"],
                question=s["question"],
                result=AnswerResult(
                    answer=s["result"]["answer"],
                    sources=[Source(**src) for src in s["result"]["sources"]],
                    prompt_version=s["result"]["prompt_version"],
                    contexts=s["result"]["contexts"],
                ),
                grounding=s["grounding"],
            )
            for s in data["sections"]
        ],
        synthesis=data["synthesis"],
        prompt_version=data["prompt_version"],
    )


def _save_cache(result: ThesisResult, fingerprint: str) -> None:
    path = _cache_path(result.ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fingerprint": fingerprint,
        "ticker": result.ticker,
        "factors": result.factors.model_dump(),
        "sections": [
            {
                "topic": s.topic,
                "question": s.question,
                "result": asdict(s.result),
                "grounding": s.grounding,
            }
            for s in result.sections
        ],
        "synthesis": result.synthesis,
        "prompt_version": result.prompt_version,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def build_thesis(ticker: str, llm_provider: str | None = None) -> ThesisResult:
    ticker = ticker.upper()

    # A thesis run costs several LLM calls (~minutes); reuse until the
    # ticker's ingested filings change.
    fingerprint = _corpus_fingerprint(ticker)
    cached = _load_cached(ticker, fingerprint)
    if cached is not None:
        return cached

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
    started = time.perf_counter()
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
    provider = llm_provider or settings.llm_provider
    usage = getattr(synthesis, "usage_metadata", None) or {}
    record_request(
        {
            "ticker": ticker,
            "llm": provider,
            "model": {
                "gemini": settings.gemini_model,
                "nvidia": settings.nvidia_model,
                "ollama": settings.ollama_model,
            }.get(provider, settings.ollama_model),
            "prompt_version": PROMPT_VERSION,
            "llm_ms": round((time.perf_counter() - started) * 1000),
            "total_ms": round((time.perf_counter() - started) * 1000),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "citation_coverage": citation_coverage(str(synthesis.content)),
            "refused": False,
            "n_sources": sum(len(s.result.sources) for s in sections),
        }
    )

    result = ThesisResult(
        ticker=ticker,
        factors=factors,
        sections=sections,
        synthesis=str(synthesis.content),
        prompt_version=PROMPT_VERSION,
    )
    _save_cache(result, fingerprint)
    return result
