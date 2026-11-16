"""Phase-1 seams: hosted embeddings client and the ChunkStore interface.
All offline: httpx runs over a MockTransport, the store is a fake."""

import json

import httpx
import pytest

import stockrag.ingestion.pipeline as pipeline
import stockrag.rag.store as store_mod
from stockrag.config import PROJECT_ROOT
from stockrag.rag.embed import NvidiaEmbeddings


def _fake_nim(calls: list[dict]):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append({"auth": request.headers["Authorization"], **body})
        # Return out of order to check the client sorts by index.
        data = [
            {"index": i, "embedding": [float(len(text)), float(i)]}
            for i, text in enumerate(body["input"])
        ]
        return httpx.Response(200, json={"data": list(reversed(data))})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_nvidia_embeddings_batches_and_input_types():
    calls: list[dict] = []
    emb = NvidiaEmbeddings(
        model="m", url="https://nim.test/v1/embeddings", api_key="k", batch_size=2, client=_fake_nim(calls)
    )
    vecs = emb.embed_documents(["a", "bb", "ccc"])
    assert vecs == [[1.0, 0.0], [2.0, 1.0], [3.0, 0.0]]
    assert [c["input"] for c in calls] == [["a", "bb"], ["ccc"]]
    assert {c["input_type"] for c in calls} == {"passage"}
    assert calls[0]["auth"] == "Bearer k" and calls[0]["model"] == "m"

    assert emb.embed_query("dddd") == [4.0, 0.0]
    assert calls[-1]["input_type"] == "query"


def test_nvidia_embeddings_requests_and_checks_dimensions():
    calls: list[dict] = []
    emb = NvidiaEmbeddings(
        model="m", url="https://nim.test/v1/embeddings", api_key="k", dimensions=2, client=_fake_nim(calls)
    )
    assert emb.embed_query("abc") == [3.0, 0.0]
    assert calls[0]["dimensions"] == 2

    wrong = NvidiaEmbeddings(
        model="m", url="https://nim.test/v1/embeddings", api_key="k", dimensions=1024, client=_fake_nim([])
    )
    with pytest.raises(RuntimeError, match="2-d vectors, expected 1024"):
        wrong.embed_query("abc")


def test_nvidia_embeddings_rejects_short_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.0]}]})

    emb = NvidiaEmbeddings(
        model="m", url="https://nim.test/v1/embeddings", api_key="k",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(RuntimeError, match="1 embeddings for 2 inputs"):
        emb.embed_documents(["a", "b"])


class FakeStore:
    def __init__(self, ingested: set[str] = frozenset()):
        self.ingested = set(ingested)
        self.added: list[tuple[list[str], list[dict], list[str]]] = []

    def add_chunks(self, texts, metadatas, ids):
        self.added.append((texts, metadatas, ids))

    def accession_ingested(self, accession):
        return accession in self.ingested

    def ticker_accessions(self, ticker):
        return sorted(self.ingested)


def _fixture_html() -> str:
    return (PROJECT_ROOT / "tests" / "fixtures" / "aapl_10k_excerpt.html").read_text(encoding="utf-8")


def test_ingest_html_writes_ids_and_chunk_index(monkeypatch):
    fake = FakeStore()
    monkeypatch.setattr(pipeline, "get_store", lambda: fake)

    result = pipeline.ingest_html(_fixture_html(), "aapl", accession="acc-1")

    assert len(fake.added) == 1
    texts, metas, ids = fake.added[0]
    assert result.chunks_added == len(texts) > 0
    assert ids == [f"acc-1:{i}" for i in range(len(texts))]
    assert [m["chunk_index"] for m in metas] == list(range(len(texts)))
    assert {m["ticker"] for m in metas} == {"AAPL"}


def test_ingest_html_skips_ingested_accession(monkeypatch):
    fake = FakeStore({"acc-1"})
    monkeypatch.setattr(pipeline, "get_store", lambda: fake)

    result = pipeline.ingest_html(_fixture_html(), "AAPL", accession="acc-1")

    assert result.filings_skipped == 1 and fake.added == []


def test_thesis_fingerprint_uses_store(monkeypatch):
    import stockrag.rag.thesis as thesis

    monkeypatch.setattr(thesis, "get_store", lambda: FakeStore({"b", "a"}))
    first = thesis._corpus_fingerprint("AAPL")
    monkeypatch.setattr(thesis, "get_store", lambda: FakeStore({"a", "b", "c"}))
    assert thesis._corpus_fingerprint("AAPL") != first


def test_get_store_rejects_unknown_backend(monkeypatch):
    store_mod.get_store.cache_clear()
    monkeypatch.setattr(store_mod.settings, "vector_store", "pinecone")
    try:
        with pytest.raises(ValueError, match="VECTOR_STORE"):
            store_mod.get_store()
    finally:
        store_mod.get_store.cache_clear()


def test_transient_errors_are_retried_and_client_errors_are_not():
    from stockrag.rag.embed import _transient

    req = httpx.Request("POST", "https://nim.test")

    def status_error(code: int) -> httpx.HTTPStatusError:
        return httpx.HTTPStatusError("x", request=req, response=httpx.Response(code, request=req))

    assert _transient(httpx.ConnectTimeout("t"))
    assert _transient(status_error(429)) and _transient(status_error(503))
    assert not _transient(status_error(400)) and not _transient(status_error(401))
    assert not _transient(RuntimeError("NVIDIA_API_KEY is not set"))


def test_ingest_clears_cached_bm25_index(monkeypatch):
    """A ticker asked about before ingest caches 'no BM25 corpus'; ingest must drop it."""
    import stockrag.rag.retrieve as retrieve
    from stockrag.ingestion import pipeline

    calls = []
    monkeypatch.setattr(retrieve._bm25_retriever, "cache_clear", lambda: calls.append(1))
    pipeline._add_chunks(FakeStore(), "acc-1", ["text"], [{"ticker": "AAPL"}])
    assert calls == [1]
