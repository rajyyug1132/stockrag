"""AUTO_INGEST_TICKERS: background ingest at startup via the app lifespan."""

from fastapi.testclient import TestClient

import stockrag.api.main as api_main
from stockrag.ingestion.pipeline import IngestResult


def test_parse_tickers():
    assert api_main._parse_tickers(" aapl, MSFT ,,aapl ") == ["AAPL", "MSFT"]
    assert api_main._parse_tickers("") == []


def _stub(calls):
    def fake_ingest(ticker, *args, **kwargs):
        calls.append(ticker)
        if ticker == "BAD":
            raise RuntimeError("boom")
        return IngestResult(filings_ingested=1, filings_skipped=0, chunks_added=5)

    return fake_ingest


def test_lifespan_ingests_in_background_and_survives_failure(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(api_main.settings, "auto_ingest_tickers", "AAPL,BAD,MSFT")
    monkeypatch.setattr(api_main, "ingest_ticker", _stub(calls))

    with TestClient(api_main.app) as client:
        assert client.get("/health").status_code == 200
        thread = api_main.auto_ingest_thread
        assert thread is not None and thread.daemon
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert calls == ["AAPL", "BAD", "MSFT"]
        assert client.get("/health").json() == {"status": "ok"}


def test_lifespan_noop_when_empty(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(api_main.settings, "auto_ingest_tickers", "")
    monkeypatch.setattr(api_main, "ingest_ticker", _stub(calls))

    with TestClient(api_main.app) as client:
        assert client.get("/health").status_code == 200
        assert api_main.auto_ingest_thread is None
    assert calls == []
