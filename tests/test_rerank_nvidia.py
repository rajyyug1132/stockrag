"""NvidiaReranker: order by logit, cut to top_n, fall back to local on error. No network."""

import httpx
import pytest
from langchain_core.documents import Document

import stockrag.rag.rerank as rerank
from stockrag.config import settings

DOCS = [Document(page_content=f"chunk {i}") for i in range(4)]


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("POST", settings.nvidia_rerank_url)
            raise httpx.HTTPStatusError("boom", request=req, response=httpx.Response(self.status_code))

    def json(self):
        return self._payload


class FakeLocal:
    def __init__(self, top_n):
        self.top_n = top_n

    def compress_documents(self, documents, query, callbacks=None):
        return list(documents)[: self.top_n]


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_api_key", "test-key")
    monkeypatch.setattr(rerank, "_local_reranker", FakeLocal)


def test_orders_by_logit_and_cuts_top_n(monkeypatch, with_key):
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, json=json, auth=headers["Authorization"])
        # Deliberately unsorted: the reranker must not trust server order.
        return FakeResponse({"rankings": [
            {"index": 0, "logit": -3.0},
            {"index": 2, "logit": 1.5},
            {"index": 3, "logit": 0.2},
            {"index": 1, "logit": -9.0},
        ]})

    monkeypatch.setattr(rerank.httpx, "post", fake_post)
    out = rerank.NvidiaReranker(top_n=2).compress_documents(DOCS, "q")

    assert [d.page_content for d in out] == ["chunk 2", "chunk 3"]
    assert sent["url"] == settings.nvidia_rerank_url
    assert sent["auth"] == "Bearer test-key"
    assert sent["json"]["query"] == {"text": "q"}
    assert sent["json"]["passages"][1] == {"text": "chunk 1"}
    assert sent["json"]["model"] == settings.nvidia_rerank_model


@pytest.mark.parametrize("failure", ["http_500", "timeout", "bad_payload"])
def test_falls_back_to_local_on_error(monkeypatch, with_key, failure):
    def fake_post(url, headers, json, timeout):
        if failure == "timeout":
            raise httpx.ReadTimeout("slow")
        if failure == "http_500":
            return FakeResponse({}, status=500)
        return FakeResponse({"unexpected": True})

    monkeypatch.setattr(rerank.httpx, "post", fake_post)
    out = rerank.NvidiaReranker(top_n=3).compress_documents(DOCS, "q")
    assert [d.page_content for d in out] == ["chunk 0", "chunk 1", "chunk 2"]


def test_missing_key_falls_back_without_calling(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_api_key", "")
    monkeypatch.setattr(rerank, "_local_reranker", FakeLocal)
    monkeypatch.setattr(rerank.httpx, "post", lambda *a, **k: pytest.fail("network call"))
    out = rerank.NvidiaReranker(top_n=1).compress_documents(DOCS, "q")
    assert [d.page_content for d in out] == ["chunk 0"]


def test_with_reranker_picks_provider(monkeypatch):
    from langchain_core.retrievers import BaseRetriever

    class Empty(BaseRetriever):
        def _get_relevant_documents(self, query, *, run_manager):
            return []

    from langchain_core.documents import BaseDocumentCompressor

    class LocalStub(BaseDocumentCompressor):
        def compress_documents(self, documents, query, callbacks=None):
            return documents

    monkeypatch.setattr(rerank, "_local_reranker", lambda top_n: LocalStub())

    monkeypatch.setattr(settings, "reranker_provider", "nvidia")
    nvidia = rerank.with_reranker(Empty(), top_n=4).base_compressor
    assert isinstance(nvidia, rerank.NvidiaReranker) and nvidia.top_n == 4

    monkeypatch.setattr(settings, "reranker_provider", "local")
    assert isinstance(rerank.with_reranker(Empty(), top_n=4).base_compressor, LocalStub)
