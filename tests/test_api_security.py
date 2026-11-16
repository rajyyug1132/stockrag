"""Public-API hardening: rate limit, input validation, ingest token, upload cap."""

import pytest
from fastapi.testclient import TestClient

import stockrag.api.main as api_main
from stockrag.ingestion.pipeline import IngestResult
from stockrag.rag.answer import AnswerResult

S = api_main.settings


def fake_ask(question, ticker, llm_provider=None):
    return AnswerResult(answer="ok", sources=[], prompt_version="v", contexts=[])


@pytest.fixture
def client(monkeypatch):
    api_main._hits.clear()
    monkeypatch.setattr(api_main, "rag_ask", fake_ask)
    monkeypatch.setattr(api_main, "ingest_ticker", lambda *a, **k: IngestResult(1, 0, 5))
    monkeypatch.setattr(api_main, "ingest_pdf", lambda *a, **k: IngestResult(1, 0, 3))
    yield TestClient(api_main.app)
    api_main._hits.clear()


def ask(client, headers=None, **body):
    return client.post("/ask", json={"question": "q", "ticker": "AAPL", **body}, headers=headers or {})


def test_rate_limit_429_with_retry_after(client, monkeypatch):
    monkeypatch.setattr(S, "rate_limit_per_minute", 2)
    assert [ask(client).status_code for _ in range(2)] == [200, 200]
    resp = ask(client)
    assert resp.status_code == 429
    assert 1 <= int(resp.headers["retry-after"]) <= 61


def test_rate_limit_off_at_zero(client, monkeypatch):
    monkeypatch.setattr(S, "rate_limit_per_minute", 0)
    assert all(ask(client).status_code == 200 for _ in range(5))


def test_client_ip_header_only_when_configured(client, monkeypatch):
    monkeypatch.setattr(S, "rate_limit_per_minute", 1)
    # Unconfigured: a spoofed header doesn't buy a fresh bucket.
    assert ask(client, {"x-real-ip": "1.1.1.1"}).status_code == 200
    assert ask(client, {"x-real-ip": "2.2.2.2"}).status_code == 429
    # Configured (Vercel overwrites it): buckets are per header value.
    monkeypatch.setattr(S, "client_ip_header", "x-real-ip")
    assert ask(client, {"x-real-ip": "3.3.3.3"}).status_code == 200
    assert ask(client, {"x-real-ip": "4.4.4.4"}).status_code == 200
    assert ask(client, {"x-real-ip": "3.3.3.3"}).status_code == 429


def test_input_validation(client, monkeypatch):
    monkeypatch.setattr(S, "rate_limit_per_minute", 0)
    monkeypatch.setattr(S, "llm_providers", "nvidia")
    assert ask(client, question="x" * 1001).status_code == 422
    assert ask(client, question="").status_code == 422
    assert ask(client, ticker="AAPL; DROP").status_code == 422
    assert ask(client, ticker="BRK.B").status_code == 200
    assert ask(client, llm="ollama").status_code == 422
    assert ask(client, llm="nvidia").status_code == 200
    assert client.get("/thesis/AAPL", params={"llm": "ollama"}).status_code == 422
    assert client.get("/factors/" + "A" * 21).status_code == 422


def test_ingest_token(client, monkeypatch):
    monkeypatch.setattr(S, "ingest_token", "s3cret")
    assert client.post("/ingest/AAPL").status_code == 403
    assert client.post("/ingest/AAPL", headers={"x-ingest-token": "wrong"}).status_code == 403
    assert client.post("/ingest/AAPL", headers={"x-ingest-token": "s3cret"}).status_code == 200
    assert client.get("/metrics").status_code == 403


def test_ingest_fails_closed_on_supabase_without_token(client, monkeypatch):
    monkeypatch.setattr(S, "ingest_token", "")
    monkeypatch.setattr(S, "vector_store", "supabase")
    assert client.post("/ingest/AAPL").status_code == 503
    assert client.get("/metrics").status_code == 503
    monkeypatch.setattr(S, "vector_store", "chroma")
    assert client.post("/ingest/AAPL").status_code == 200  # local dev stays open


def test_pdf_upload_cap(client, monkeypatch):
    monkeypatch.setattr(S, "ingest_token", "")
    monkeypatch.setattr(S, "max_upload_mb", 1)
    big = {"file": ("r.pdf", b"x" * (1024 * 1024 + 1), "application/pdf")}
    assert client.post("/ingest-pdf", data={"ticker": "TCS"}, files=big).status_code == 413
    ok = {"file": ("r.pdf", b"%PDF-1.4", "application/pdf")}
    assert client.post("/ingest-pdf", data={"ticker": "TCS"}, files=ok).status_code == 200
