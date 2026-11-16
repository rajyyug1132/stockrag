"""Thesis briefing: factor engine + RAG evidence synthesized into one document.

Ports the structured-thesis pattern (summary / bull / bear / risks, every
point evidence-cited) into StockRAG: quantitative side from the XBRL factor
report, qualitative side from citation-enforced RAG answers over filings.
"""

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import yaml

from stockrag.config import settings
from stockrag.factor_engine.report import FactorReport, build_factor_report
from stockrag.rag.answer import AnswerResult, Source, ask
from stockrag.rag.llm import get_llm
from stockrag.rag.metrics import citation_coverage, record_request
from stockrag.rag.store import get_store

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
    """Hash of the ticker's ingested accessions — cache validity key."""
    accessions = get_store().ticker_accessions(ticker)
    return hashlib.sha256("|".join(accessions).encode()).hexdigest()[:16]


def _cache_path(ticker: str):
    return settings.data_dir / "thesis" / f"{ticker}.json"


def _read_cache(ticker: str) -> dict | None:
    if settings.vector_store == "supabase":
        from stockrag.rag.supabase_store import get_client

        try:
            rows = get_client().request(
                "GET", "thesis_cache", retry=True, params={"ticker": f"eq.{ticker}", "select": "payload"}
            )
            return rows[0]["payload"] if rows else None
        except Exception:  # a cache miss is cheaper than a failed request
            return None
    path = _cache_path(ticker)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _load_cached(ticker: str, fingerprint: str) -> ThesisResult | None:
    data = _read_cache(ticker)
    if data is None:
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
    if settings.vector_store == "supabase":
        from stockrag.rag.supabase_store import get_client

        try:
            get_client().request(
                "POST", "thesis_cache", retry=True,  # idempotent upsert
                params={"on_conflict": "ticker"},
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                json={"ticker": result.ticker, "fingerprint": fingerprint, "payload": payload,
                      "updated_at": datetime.now(timezone.utc).isoformat()},
            )
        except Exception:  # the thesis is computed; failing to cache it must not fail the request
            pass
        return
    path = _cache_path(result.ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
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

    def _section(tq: tuple[str, str]) -> ThesisSection:
        topic, question = tq
        result = ask(question, ticker, llm_provider=llm_provider)
        return ThesisSection(
            topic=topic, question=question, result=result, grounding=citation_coverage(result.answer)
        )

    # First question alone: ask() builds lru_cache singletons (Chroma client, BM25,
    # cross-encoder) that aren't safe to race on a cold process. The rest run in parallel.
    first, *rest = THESIS_QUESTIONS
    sections = [_section(first)]
    with ThreadPoolExecutor(max_workers=max(len(rest), 1)) as pool:
        sections += pool.map(_section, rest)  # map keeps question order

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
