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


@pytest.mark.parametrize("store", ["supabase", "chroma", "typo"])
def test_ingest_fails_closed_without_token_whatever_the_backend(client, monkeypatch, store):
    monkeypatch.setattr(S, "ingest_token", "")
    monkeypatch.setattr(S, "vector_store", store)
    assert client.post("/ingest/AAPL").status_code == 503
    assert client.get("/metrics").status_code == 503
    monkeypatch.setattr(S, "allow_open_ingest", True)  # explicit local-dev opt-in
    assert client.post("/ingest/AAPL").status_code == 200


def test_unauthenticated_or_oversized_bodies_refused_before_parsing(client, monkeypatch):
    monkeypatch.setattr(S, "ingest_token", "s3cret")
    monkeypatch.setattr(S, "max_upload_mb", 1)
    called = []
    monkeypatch.setattr(api_main, "ingest_pdf", lambda *a, **k: called.append(1))
    small = {"file": ("r.pdf", b"%PDF-1.4", "application/pdf")}
    assert client.post("/ingest-pdf", data={"ticker": "TCS"}, files=small).status_code == 403
    big = {"file": ("r.pdf", b"x" * (3 * 1024 * 1024), "application/pdf")}
    resp = client.post("/ingest-pdf", data={"ticker": "TCS"}, files=big, headers={"x-ingest-token": "s3cret"})
    assert resp.status_code == 413 and resp.json() == {"detail": "Request body too large."}
    assert called == []


def test_small_routes_cap_and_lengthless_bodies(client, monkeypatch):
    monkeypatch.setattr(S, "rate_limit_per_minute", 0)
    big = client.post("/ask", content=b"{" + b" " * (70 * 1024) + b"}", headers={"content-type": "application/json"})
    assert big.status_code == 413

    def chunks():
        yield b'{"question": "q", "ticker": "AAPL"}'

    assert client.post("/ask", content=chunks(), headers={"content-type": "application/json"}).status_code == 411


def test_guard_responses_keep_cors_headers(client, monkeypatch):
    monkeypatch.setattr(S, "ingest_token", "s3cret")
    origin = S.cors_origins.split(",")[0]
    resp = client.post("/ingest/AAPL", headers={"origin": origin})
    assert resp.status_code == 403 and resp.headers["access-control-allow-origin"] == origin


def test_token_guessing_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(S, "ingest_token", "s3cret")
    monkeypatch.setattr(S, "rate_limit_per_minute", 2)
    codes = [client.post("/ingest/AAPL", headers={"x-ingest-token": "guess"}).status_code for _ in range(3)]
    assert codes == [403, 403, 429]


def test_rate_limit_uses_rightmost_forwarded_entry(client, monkeypatch):
    monkeypatch.setattr(S, "rate_limit_per_minute", 1)
    monkeypatch.setattr(S, "client_ip_header", "x-forwarded-for")
    # The client controls the leftmost entries; the proxy appends the real one.
    assert ask(client, {"x-forwarded-for": "6.6.6.6, 9.9.9.9"}).status_code == 200
    assert ask(client, {"x-forwarded-for": "7.7.7.7, 9.9.9.9"}).status_code == 429


def test_thesis_concurrency_cap(client, monkeypatch):
    monkeypatch.setattr(S, "rate_limit_per_minute", 0)
    monkeypatch.setattr(api_main, "_thesis_slots", api_main.threading.BoundedSemaphore(1))
    api_main._thesis_slots.acquire()  # one thesis already running
    try:
        resp = client.get("/thesis/AAPL")
        assert resp.status_code == 429 and resp.headers["Retry-After"] == "30"
    finally:
        api_main._thesis_slots.release()


def test_pdf_upload_cap(client, monkeypatch):
    monkeypatch.setattr(S, "ingest_token", "")
    monkeypatch.setattr(S, "allow_open_ingest", True)
    monkeypatch.setattr(S, "max_upload_mb", 1)
    big = {"file": ("r.pdf", b"x" * (1024 * 1024 + 1), "application/pdf")}
    assert client.post("/ingest-pdf", data={"ticker": "TCS"}, files=big).status_code == 413
    ok = {"file": ("r.pdf", b"%PDF-1.4", "application/pdf")}
    assert client.post("/ingest-pdf", data={"ticker": "TCS"}, files=ok).status_code == 200
