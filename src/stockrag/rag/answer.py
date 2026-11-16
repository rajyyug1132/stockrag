import re
import time
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from stockrag.config import settings
from stockrag.ingestion.chunk import encoding
from stockrag.rag.expand import _stitch, expand_docs
from stockrag.rag.llm import get_llm
from stockrag.rag.metrics import citation_coverage, estimate_cost_usd, record_request
from stockrag.rag.prompts import load_prompt
from stockrag.rag.store import get_vector_store
from stockrag.rag.tracing import tracing_callbacks

DEFAULT_K = 6
CITATION_RE = re.compile(r"\s*\[(\d+)\]")
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
    """Hybrid keyword+vector retrieval (RRF fusion) rescored by the reranker
    down to the top-k chunks. Chroma fuses BM25 and vector search in process;
    Supabase fuses full-text and pgvector search in Postgres."""
    from stockrag.rag.rerank import with_reranker

    if settings.vector_store == "supabase":
        from stockrag.rag.supabase_store import SupabaseRetriever

        return with_reranker(SupabaseRetriever(ticker=ticker, window=settings.parent_window), top_n=k)

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


def _finalize(raw: str, n_sources: int) -> str:
    """Turn raw model output into the answer we are willing to show: strip
    leaked reasoning, drop citations that point at no retrieved source, and
    refuse if nothing cited survives. Shared by ask() and ask_stream() so the
    two paths cannot drift."""
    answer = THINK_BLOCK_RE.sub("", raw).strip()
    # A [14] against six sources is a hallucinated citation, not grounding:
    # remove it so the sentence counts as uncited instead of passing the gate.
    answer = CITATION_RE.sub(
        lambda m: m.group(0) if 1 <= int(m.group(1)) <= n_sources else "", answer
    )
    return answer if CITATION_RE.search(answer) else NO_CONTEXT_MESSAGE


def _widen(doc: Document) -> Document:
    """Doc whose page_content is its neighbours (hit included) stitched in
    char order; metadata, and so the citation, stays the hit's own."""
    neighbours = doc.metadata.get("neighbours") or []
    if not neighbours:
        return doc
    parts = sorted((n["char_start"], n["char_end"], n["content"]) for n in neighbours)
    return Document(page_content=_stitch(parts), metadata=doc.metadata)


def _context_docs(docs: list[Document], ticker: str, provider: str) -> list[Document]:
    """Small-to-big: widen each reranked chunk to its section neighbours so
    the LLM sees surrounding context; citations still map to the retrieved
    chunk's metadata.

    Ollama runs a fixed context window and truncates an oversized prompt from
    the front — which is where the rules and the question are — so for it the
    context is shrunk to fit: unwidened chunks first, then fewer of them
    (lowest-ranked dropped first)."""
    if docs and all("neighbours" in d.metadata for d in docs):
        # Supabase returned each hit's section neighbours with it: stitch them
        # here instead of loading the whole ticker to find them.
        expanded = [_widen(d) for d in docs]
    else:
        expanded = expand_docs(docs, ticker, window=settings.parent_window)
    if provider != "ollama":
        return expanded

    def tokens(ds: list[Document]) -> int:
        return sum(len(encoding().encode(d.page_content)) for d in ds)

    budget = settings.ollama_context_tokens
    if tokens(expanded) <= budget:
        return expanded
    while len(docs) > 1 and tokens(docs) > budget:
        docs = docs[:-1]
    return docs


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

        docs = _context_docs(docs, ticker, provider)
        context, sources = _format_docs(docs)
        chain = load_prompt(prompt_version) | get_llm(llm_provider)
        llm_started = time.perf_counter()
        message = chain.invoke({"question": question, "context": context}, config=config)
        metric["llm_ms"] = round((time.perf_counter() - llm_started) * 1000)

        answer = _finalize(str(message.content), len(sources))

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


def ask_stream(
    question: str,
    ticker: str,
    prompt_version: str = "v3",
    retriever: BaseRetriever | None = None,
    llm_provider: str | None = None,
):
    """Like ask(), but yields answer tokens (str) as they arrive, then a final
    AnswerResult. The final result applies the same think-strip + citation gate
    as ask(), so the client must replace streamed text with the final answer.
    Tokens inside a leading <think> block are held back, never streamed."""
    provider = llm_provider or settings.llm_provider
    model = {
        "gemini": settings.gemini_model,
        "nvidia": settings.nvidia_model,
        "ollama": settings.ollama_model,
    }.get(provider, settings.ollama_model)
    config = {
        "callbacks": tracing_callbacks(),
        "run_name": "stockrag-ask-stream",
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
            yield AnswerResult(
                answer=NO_CONTEXT_MESSAGE, sources=[], prompt_version=prompt_version, contexts=[]
            )
            return

        docs = _context_docs(docs, ticker, provider)
        context, sources = _format_docs(docs)
        chain = load_prompt(prompt_version) | get_llm(llm_provider)
        llm_started = time.perf_counter()

        buffer = ""
        emitted = 0
        thinking: bool | None = None  # unknown until first non-space content
        for chunk in chain.stream({"question": question, "context": context}, config=config):
            buffer += str(chunk.content)
            if thinking is None and buffer.lstrip():
                thinking = buffer.lstrip().startswith("<think")
            if thinking:
                if "</think>" in buffer:
                    buffer = THINK_BLOCK_RE.sub("", buffer)
                    thinking = False
                    emitted = 0
                else:
                    continue
            if len(buffer) > emitted:
                yield buffer[emitted:]
                emitted = len(buffer)
        metric["llm_ms"] = round((time.perf_counter() - llm_started) * 1000)

        # The buffer can still hold reasoning when the model emitted a bare
        # </think> with no opening tag (qwen3 does); _finalize strips it.
        answer = _finalize(buffer, len(sources))

        # ponytail: streaming chunks don't carry usage_metadata reliably; token
        # counts/cost stay unrecorded for streamed asks — add aggregation if
        # metrics need them.
        metric.update(
            total_ms=round((time.perf_counter() - started) * 1000),
            citation_coverage=citation_coverage(answer),
            refused=answer == NO_CONTEXT_MESSAGE,
            n_sources=len(sources),
        )
        record_request(metric)

        yield AnswerResult(
            answer=answer,
            sources=sources,
            prompt_version=prompt_version,
            contexts=[doc.page_content for doc in docs],
        )
    except Exception as exc:
        metric.update(error=type(exc).__name__, total_ms=round((time.perf_counter() - started) * 1000))
        record_request(metric)
        raise
