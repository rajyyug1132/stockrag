"""Supabase backend, offline: PostgREST is an httpx MockTransport, embeddings
are fakes. Plus the import check the serverless API depends on."""

import json
import logging
import os
import subprocess
import sys

import httpx
import pytest
from langchain_core.documents import Document

import stockrag.rag.answer as answer
import stockrag.rag.rerank as rerank
from stockrag.config import settings
from stockrag.rag.supabase_store import SupabaseClient, SupabaseError, SupabaseRetriever, SupabaseStore

URL = "https://proj.supabase.test"


class FakeEmbeddings:
    def embed_documents(self, texts):
        return [[float(i), 0.5] for i, _ in enumerate(texts)]

    def embed_query(self, text):
        return [0.25, 0.75]


def _client(handler, key="sb_secret_test"):
    calls: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    http = httpx.Client(transport=httpx.MockTransport(record))
    return SupabaseClient(URL, key, client=http), calls


def _meta(i: int, accession: str = "acc") -> dict:
    return {
        "ticker": "AAPL", "form": "10-K", "filing_date": "2025-10-31", "accession": accession,
        "section": "Item 1A", "chunk_index": i, "char_start": i * 10, "char_end": i * 10 + 15,
    }


def test_add_chunks_upserts_full_rows_in_batches_with_row_zero_last(monkeypatch):
    monkeypatch.setattr("stockrag.rag.supabase_store.INSERT_BATCH", 2)
    client, calls = _client(lambda r: httpx.Response(201))
    store = SupabaseStore(client=client, embeddings=FakeEmbeddings())

    store.add_chunks(["t0", "t1", "t2"], [_meta(0), _meta(1), _meta(2)], ["acc:0", "acc:1", "acc:2"])

    assert len(calls) == 2
    for req in calls:
        assert req.method == "POST" and req.url.path == "/rest/v1/chunks"
        assert req.url.params["on_conflict"] == "id"
        assert "resolution=merge-duplicates" in req.headers["Prefer"]
    batches = [json.loads(r.content) for r in calls]
    assert [row["id"] for b in batches for row in b] == ["acc:1", "acc:2", "acc:0"]
    row0 = batches[-1][0]
    assert row0 == {
        "id": "acc:0", "content": "t0", "embedding": [0.0, 0.5], "ticker": "AAPL", "form": "10-K",
        "filing_date": "2025-10-31", "accession": "acc", "section": "Item 1A",
        "chunk_index": 0, "char_start": 0, "char_end": 15,
    }


def test_headers_secret_key_vs_legacy_jwt():
    client, calls = _client(lambda r: httpx.Response(200, json=[]))
    client.request("GET", "chunks")
    assert calls[0].headers["apikey"] == "sb_secret_test"
    assert "Authorization" not in calls[0].headers

    client, calls = _client(lambda r: httpx.Response(200, json=[]), key="eyJhbGciOi.legacy")
    client.request("GET", "chunks")
    assert calls[0].headers["Authorization"] == "Bearer eyJhbGciOi.legacy"


def test_accession_ingested_queries_row_zero():
    rows = {"eq.done:0": [{"id": "done:0"}]}
    client, calls = _client(lambda r: httpx.Response(200, json=rows.get(r.url.params["id"], [])))
    store = SupabaseStore(client=client, embeddings=FakeEmbeddings())
    assert store.accession_ingested("done") is True
    assert store.accession_ingested("new") is False
    assert calls[0].url.params["select"] == "id"


@pytest.mark.parametrize("payload", [["b", "a"], [{"ticker_accessions": "b"}, {"ticker_accessions": "a"}]])
def test_ticker_accessions_rpc_either_shape(payload):
    client, calls = _client(lambda r: httpx.Response(200, json=payload))
    assert SupabaseStore(client=client, embeddings=FakeEmbeddings()).ticker_accessions("AAPL") == ["a", "b"]
    assert calls[0].url.path == "/rest/v1/rpc/ticker_accessions"
    assert json.loads(calls[0].content) == {"p_ticker": "AAPL"}


def test_errors_name_the_call_not_the_key():
    client, _ = _client(lambda r: httpx.Response(401, json={"message": "Invalid API key"}), key="sb_secret_xyz")
    with pytest.raises(SupabaseError) as exc:
        client.rpc("hybrid_search", {})
    assert "rpc/hybrid_search -> HTTP 401: Invalid API key" in str(exc.value)
    assert "sb_secret_xyz" not in str(exc.value)


def test_transport_errors_never_carry_the_key():
    # httpx's LocalProtocolError quotes an illegal header value verbatim.
    def echo_key(request):
        raise httpx.LocalProtocolError(f"Illegal header value {request.headers['apikey']!r}")

    client, calls = _client(echo_key, key="sb_secret_leaky")
    with pytest.raises(SupabaseError) as exc:
        client.rpc("ticker_accessions", {"p_ticker": "AAPL"})
    assert str(exc.value) == "Supabase POST rpc/ticker_accessions: LocalProtocolError"
    assert exc.value.__context__ is None and exc.value.__cause__ is None
    assert len(calls) == 2  # rpc retries once


def test_pasted_key_whitespace_is_stripped():
    client, calls = _client(lambda r: httpx.Response(200, json=[]), key="  sb_secret_x\n")
    client.request("GET", "chunks")
    assert calls[0].headers["apikey"] == "sb_secret_x"


def test_retry_only_where_asked():
    state = {"n": 0}

    def flaky(request):
        state["n"] += 1
        if state["n"] == 1:
            raise httpx.RemoteProtocolError("stale keep-alive socket")
        return httpx.Response(200, json=["a"])

    client, _ = _client(flaky)
    assert client.rpc("ticker_accessions", {"p_ticker": "AAPL"}) == ["a"]

    state["n"] = 0
    client, _ = _client(flaky)
    with pytest.raises(SupabaseError, match="RemoteProtocolError"):
        client.request("POST", "anything")


@pytest.mark.parametrize(
    "response, match",
    [
        (httpx.Response(502, json=["gateway", "list"]), r"HTTP 502: \['gateway', 'list'\]"),
        (httpx.Response(500, text="<html>oops</html>"), "HTTP 500: <html>oops</html>"),
        (httpx.Response(200, text="<html>login</html>"), "non-JSON response"),
    ],
)
def test_odd_responses_become_supabase_errors(response, match):
    client, _ = _client(lambda r: response)
    with pytest.raises(SupabaseError, match=match):
        client.request("GET", "chunks")


def test_nul_characters_are_stripped_before_insert():
    client, calls = _client(lambda r: httpx.Response(201))
    SupabaseStore(client=client, embeddings=FakeEmbeddings()).add_chunks(["a\x00b"], [_meta(0)], ["acc:0"])
    assert json.loads(calls[0].content)[0]["content"] == "ab"


def test_missing_config_and_local_embeddings_are_rejected(monkeypatch):
    with pytest.raises(SupabaseError, match="SUPABASE_URL and SUPABASE_SERVICE_KEY"):
        SupabaseClient("", "")
    monkeypatch.setattr(settings, "embedding_provider", "local")
    client, _ = _client(lambda r: httpx.Response(201))
    with pytest.raises(SupabaseError, match="EMBEDDING_PROVIDER=nvidia"):
        SupabaseStore(client=client).add_chunks(["t"], [_meta(0)], ["acc:0"])


def _hit(i: int, neighbours: list[dict]) -> dict:
    return {"id": f"acc:{i}", **_meta(i), "content": f"chunk {i}", "score": 0.03 - i / 1000,
            "neighbours": neighbours}


def test_retriever_calls_hybrid_search_and_maps_rows():
    nb = [{"char_start": 0, "char_end": 15, "content": "chunk 0"}]
    client, calls = _client(lambda r: httpx.Response(200, json=[_hit(0, nb), _hit(1, [])]))
    retriever = SupabaseRetriever(ticker="aapl", n=12, window=2, client=client, embeddings=FakeEmbeddings())

    docs = retriever.invoke("What are the risks?")

    body = json.loads(calls[0].content)
    assert calls[0].url.path == "/rest/v1/rpc/hybrid_search"
    assert body == {"q": "What are the risks?", "q_embedding": [0.25, 0.75], "p_ticker": "AAPL", "n": 12, "win": 2}
    assert [d.page_content for d in docs] == ["chunk 0", "chunk 1"]
    assert docs[0].metadata["neighbours"] == nb
    assert docs[0].metadata["accession"] == "acc" and docs[0].metadata["chunk_index"] == 0
    assert docs[1].metadata["neighbours"] == []


def test_context_docs_stitches_neighbours_without_touching_chroma(monkeypatch):
    def no_chroma(*args, **kwargs):
        raise AssertionError("expand_docs must not run when neighbours are present")

    monkeypatch.setattr(answer, "expand_docs", no_chroma)
    hit = Document(page_content="EFGHIJ", metadata={
        "section": "Item 1A",
        "neighbours": [  # out of order on purpose; overlap "EF" must not repeat
            {"char_start": 4, "char_end": 10, "content": "EFGHIJ"},
            {"char_start": 0, "char_end": 6, "content": "ABCDEF"},
        ],
    })
    lonely = Document(page_content="solo", metadata={"neighbours": []})

    out = answer._context_docs([hit, lonely], "AAPL", provider="nvidia")

    assert [d.page_content for d in out] == ["ABCDEFGHIJ", "solo"]
    assert out[0].metadata == hit.metadata  # citation still points at the hit


def test_get_retriever_uses_supabase_with_reranker(monkeypatch):
    monkeypatch.setattr(settings, "vector_store", "supabase")
    monkeypatch.setattr(settings, "reranker_provider", "nvidia")
    monkeypatch.setattr(settings, "parent_window", 2)
    r = answer.get_retriever("AAPL", k=4)
    assert isinstance(r.base_retriever, SupabaseRetriever)
    assert r.base_retriever.window == 2
    assert isinstance(r.base_compressor, rerank.NvidiaReranker) and r.base_compressor.top_n == 4


def test_reranker_keeps_fused_order_without_local_cross_encoder(monkeypatch, caplog):
    monkeypatch.setattr(settings, "nvidia_api_key", "")  # NVIDIA path fails at once

    def no_local(top_n):
        raise ImportError("No module named 'sentence_transformers'")

    monkeypatch.setattr(rerank, "_local_reranker", no_local)
    docs = [Document(page_content=f"c{i}") for i in range(5)]
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        out = rerank.NvidiaReranker(top_n=3).compress_documents(docs, "q")
    assert [d.page_content for d in out] == ["c0", "c1", "c2"]
    assert "keeping fused retrieval order" in caplog.text


HEAVY = ["chromadb", "torch", "sentence_transformers", "langchain_huggingface", "rank_bm25",
         "transformers", "langchain_chroma"]


def test_api_imports_and_answers_retrieval_without_heavy_modules():
    """The slim (serverless) install has none of HEAVY; blocking them in
    sys.modules makes any import of them fail like a missing package. Then a
    real query runs through hybrid_search (mocked transport) and the reranker:
    NVIDIA fails (no key), the local cross-encoder genuinely can't import, so
    the fused order is kept."""
    code = f"""
import sys
for m in {HEAVY!r}:
    sys.modules[m] = None
import httpx
import stockrag.api.main
from stockrag.rag.answer import get_retriever
from stockrag.rag.supabase_store import SupabaseClient

r = get_retriever("AAPL", k=2)
assert type(r.base_retriever).__name__ == "SupabaseRetriever", r
# Importing these loads transformers/torch whenever they are installed.
for m in ("langchain.retrievers", "langchain_community", "stockrag.rag.retrieve"):
    assert m not in sys.modules, m

rows = [{{"id": f"a:{{i}}", "ticker": "AAPL", "form": "10-K", "filing_date": "", "accession": "a",
         "section": "s", "chunk_index": i, "char_start": i, "char_end": i + 1, "content": f"c{{i}}",
         "score": 1.0 - i / 10, "neighbours": []}} for i in range(3)]
http = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=rows)))
r.base_retriever.client = SupabaseClient("{URL}", "sb_secret_test", client=http)

class Emb:
    def embed_query(self, text):
        return [0.0] * 1024

r.base_retriever.embeddings = Emb()
docs = r.invoke("What are the risks?")
assert [d.page_content for d in docs] == ["c0", "c1"], docs
print("ok")
"""
    env = {**os.environ, "VECTOR_STORE": "supabase", "EMBEDDING_PROVIDER": "nvidia", "RERANKER_PROVIDER": "nvidia",
           "SUPABASE_URL": URL, "SUPABASE_SERVICE_KEY": "sb_secret_test", "NVIDIA_API_KEY": ""}
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=120)
    assert res.returncode == 0 and res.stdout.strip().endswith("ok"), res.stderr[-2000:]
