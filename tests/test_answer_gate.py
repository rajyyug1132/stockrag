"""The answer gate: leaked reasoning is stripped, citations must point at a
retrieved source, and Ollama's context is shrunk to fit its window."""

from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda

import stockrag.rag.answer as answer
from stockrag.rag.answer import NO_CONTEXT_MESSAGE, AnswerResult, _context_docs, _finalize


def test_finalize_strips_reasoning_without_opening_tag():
    raw = "Hmm, the user never asked a question [1]. </think>\nRevenue grew [1]."
    assert _finalize(raw, n_sources=2) == "Revenue grew [1]."


def test_finalize_drops_out_of_range_citations():
    raw = "Apple faces antitrust suits. [14] It changed the App Store [2][9]."
    assert _finalize(raw, n_sources=6) == "Apple faces antitrust suits. It changed the App Store [2]."


def test_finalize_refuses_when_only_invalid_citations():
    assert _finalize("Apple faces antitrust suits [14]. See [0].", n_sources=6) == NO_CONTEXT_MESSAGE
    assert _finalize("No citations at all.", n_sources=6) == NO_CONTEXT_MESSAGE


def _docs(n: int, words: int) -> list[Document]:
    return [Document(page_content=f"chunk{i} " + "word " * words, metadata={"i": i}) for i in range(n)]


def _widen(docs, ticker, window):
    return [Document(page_content=d.page_content * 3, metadata=d.metadata) for d in docs]


def test_context_docs_keeps_expansion_for_hosted_providers(monkeypatch):
    monkeypatch.setattr(answer, "expand_docs", _widen)
    monkeypatch.setattr(answer.settings, "ollama_context_tokens", 100)
    small = _docs(6, 50)
    out = _context_docs(small, "AAPL", "nvidia")
    assert [d.page_content for d in out] == [d.page_content * 3 for d in small]


def test_context_docs_shrinks_for_ollama(monkeypatch):
    monkeypatch.setattr(answer, "expand_docs", _widen)
    small = _docs(6, 50)  # ~52 tokens each

    # Fits widened: untouched.
    monkeypatch.setattr(answer.settings, "ollama_context_tokens", 10_000)
    assert len(_context_docs(small, "AAPL", "ollama")[0].page_content) == len(small[0].page_content) * 3

    # Widened overflows, unwidened fits: all six, unwidened.
    monkeypatch.setattr(answer.settings, "ollama_context_tokens", 400)
    assert _context_docs(small, "AAPL", "ollama") == small

    # Even unwidened overflows: lowest-ranked chunks dropped, top one kept.
    monkeypatch.setattr(answer.settings, "ollama_context_tokens", 120)
    assert _context_docs(small, "AAPL", "ollama") == small[:2]
    monkeypatch.setattr(answer.settings, "ollama_context_tokens", 1)
    assert _context_docs(small, "AAPL", "ollama") == small[:1]


def test_ask_stream_final_answer_is_gated(monkeypatch):
    """The exact failure seen with qwen3: reasoning closed by a bare </think>
    and citations to sources that do not exist."""
    raw = "They never stated a question. </think>\nCourt issued an injunction. [1]\nApple faces suits. [14]"
    monkeypatch.setattr(answer, "expand_docs", lambda docs, ticker, window: docs)
    monkeypatch.setattr(answer, "load_prompt", lambda version: RunnableLambda(lambda x: "prompt"))
    monkeypatch.setattr(answer, "get_llm", lambda provider=None: FakeListChatModel(responses=[raw]))
    recorded = []
    monkeypatch.setattr(answer, "record_request", recorded.append)

    docs = [Document(page_content="ctx", metadata={"form": "10-K"})]
    events = list(answer.ask_stream("q", "AAPL", retriever=RunnableLambda(lambda q: docs), llm_provider="ollama"))

    final = events[-1]
    assert isinstance(final, AnswerResult)
    assert final.answer == "Court issued an injunction. [1]\nApple faces suits."
    assert recorded[0]["refused"] is False
    assert recorded[0]["citation_coverage"] == 0.5
