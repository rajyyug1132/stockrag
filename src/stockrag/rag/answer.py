import re
import time
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from stockrag.config import settings
from stockrag.rag.llm import get_llm
from stockrag.rag.metrics import citation_coverage, estimate_cost_usd, record_request
from stockrag.rag.prompts import load_prompt
from stockrag.rag.store import get_vector_store
from stockrag.rag.tracing import tracing_callbacks

DEFAULT_K = 6
CITATION_RE = re.compile(r"\[\d+\]")
# Thinking models (qwen3) sometimes leak reasoning despite reasoning=False;
# drop everything up to the last closing think tag.
THINK_BLOCK_RE = re.compile(r"^.*</think>\s*", re.DOTALL)
NO_CONTEXT_MESSAGE = "I don't have enough information in the retrieved filings to answer this."


@dataclass(frozen=True)
class Source:
    index: int
    form: str
    filing_date: str
    section: str
    accession: str


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    sources: list[Source]
    prompt_version: str
    # Raw retrieved chunk texts, in source order; needed by the Ragas
    # evaluation harness (retrieved_contexts).
    contexts: list[str]


def get_retriever(ticker: str, k: int = DEFAULT_K) -> BaseRetriever:
    """Hybrid BM25+vector retrieval (RRF fusion) rescored by a local
    cross-encoder down to the top-k chunks."""
    from stockrag.rag.rerank import with_reranker
    from stockrag.rag.retrieve import get_hybrid_retriever

    return with_reranker(get_hybrid_retriever(ticker), top_n=k)


def get_vector_only_retriever(ticker: str, k: int = DEFAULT_K) -> BaseRetriever:
    """Pure vector search, kept for A/B comparison against the hybrid path."""
    store = get_vector_store()
    return store.as_retriever(search_kwargs={"k": k, "filter": {"ticker": ticker.upper()}})


def _format_docs(docs: list[Document]) -> tuple[str, list[Source]]:
    lines: list[str] = []
    sources: list[Source] = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata
        lines.append(
            f"[{i}] ({meta.get('form')}, filed {meta.get('filing_date')}, {meta.get('section')}):\n"
            f"{doc.page_content}"
        )
        sources.append(
            Source(
                index=i,
                form=meta.get("form", ""),
                filing_date=meta.get("filing_date", ""),
                section=meta.get("section", ""),
                accession=meta.get("accession", ""),
            )
        )
    return "\n\n".join(lines), sources


def ask(
    question: str,
    ticker: str,
    prompt_version: str = "v3",
    retriever: BaseRetriever | None = None,
    llm_provider: str | None = None,
) -> AnswerResult:
    provider = llm_provider or settings.llm_provider
    model = {
        "gemini": settings.gemini_model,
        "nvidia": settings.nvidia_model,
        "ollama": settings.ollama_model,
    }.get(provider, settings.ollama_model)
    config = {
        "callbacks": tracing_callbacks(),
        "run_name": "stockrag-ask",
        "metadata": {"ticker": ticker.upper(), "prompt_version": prompt_version, "llm": provider},
    }
    metric: dict = {"ticker": ticker.upper(), "llm": provider, "model": model, "prompt_version": prompt_version}

    started = time.perf_counter()
    try:
        retriever = retriever or get_retriever(ticker)
        docs = retriever.invoke(question, config=config)
        metric["retrieval_ms"] = round((time.perf_counter() - started) * 1000)

        if not docs:
            metric.update(refused=True, total_ms=metric["retrieval_ms"])
            record_request(metric)
            return AnswerResult(
                answer=NO_CONTEXT_MESSAGE, sources=[], prompt_version=prompt_version, contexts=[]
            )

        context, sources = _format_docs(docs)
        chain = load_prompt(prompt_version) | get_llm(llm_provider)
        llm_started = time.perf_counter()
        message = chain.invoke({"question": question, "context": context}, config=config)
        metric["llm_ms"] = round((time.perf_counter() - llm_started) * 1000)

        answer = THINK_BLOCK_RE.sub("", str(message.content)).strip()

        # Refuse answers that dodge citation enforcement rather than trusting
        # uncited claims.
        if not CITATION_RE.search(answer):
            answer = NO_CONTEXT_MESSAGE

        usage = getattr(message, "usage_metadata", None) or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        metric.update(
            total_ms=round((time.perf_counter() - started) * 1000),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=estimate_cost_usd(model, input_tokens, output_tokens),
            citation_coverage=citation_coverage(answer),
            refused=answer == NO_CONTEXT_MESSAGE,
            n_sources=len(sources),
        )
        record_request(metric)

        return AnswerResult(
            answer=answer,
            sources=sources,
            prompt_version=prompt_version,
            contexts=[doc.page_content for doc in docs],
        )
    except Exception as exc:
        metric.update(error=type(exc).__name__, total_ms=round((time.perf_counter() - started) * 1000))
        record_request(metric)
        raise
