"""SSE framing for POST /ask/stream: token events then one done event."""

import json

from fastapi.testclient import TestClient

import stockrag.api.main as api_main
from stockrag.rag.answer import AnswerResult, Source


def fake_stream(question, ticker, llm_provider=None):
    yield "Revenue "
    yield "grew [1]."
    yield AnswerResult(
        answer="Revenue grew [1].",
        sources=[Source(index=1, form="10-K", filing_date="2024-02-14", section="Item 7", accession="x")],
        prompt_version="v3",
        contexts=["ctx"],
    )


def test_ask_stream_sse(monkeypatch):
    monkeypatch.setattr(api_main, "rag_ask_stream", fake_stream)
    client = TestClient(api_main.app)
    resp = client.post("/ask/stream", json={"question": "q", "ticker": "AAPL"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = [json.loads(e[len("data: "):]) for e in resp.text.strip().split("\n\n")]
    assert [e.get("token") for e in events[:-1]] == ["Revenue ", "grew [1]."]
    final = events[-1]
    assert final["done"] is True
    assert final["answer"] == "Revenue grew [1]."
    assert final["sources"][0]["form"] == "10-K"
