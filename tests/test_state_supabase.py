"""Server state (metrics, thesis cache) on Supabase, offline: PostgREST is an
httpx MockTransport. Also the concurrent thesis loop."""

import json
import time
from types import SimpleNamespace

import httpx

import stockrag.rag.metrics as metrics
import stockrag.rag.thesis as thesis
from stockrag.config import settings
from stockrag.factor_engine.report import FactorReport
from stockrag.rag.answer import AnswerResult
from stockrag.rag.supabase_store import SupabaseClient


def _use_supabase(monkeypatch, handler):
    calls: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    client = SupabaseClient(
        "https://proj.supabase.test", "sb_secret_test", client=httpx.Client(transport=httpx.MockTransport(record))
    )
    monkeypatch.setattr(settings, "vector_store", "supabase")
    monkeypatch.setattr("stockrag.rag.supabase_store.get_client", lambda: client)
    return calls


def test_record_request_inserts_wrapped_record(monkeypatch):
    calls = _use_supabase(monkeypatch, lambda r: httpx.Response(201))
    metrics.record_request({"total_ms": 5})
    (req,) = calls
    assert req.method == "POST" and req.url.path == "/rest/v1/request_metrics"
    assert req.headers["Prefer"] == "return=minimal"
    record = json.loads(req.content)["record"]
    assert record["total_ms"] == 5 and "timestamp" in record


def test_record_request_never_raises_when_supabase_errors(monkeypatch):
    _use_supabase(monkeypatch, lambda r: httpx.Response(500, json={"message": "boom"}))
    metrics.record_request({"total_ms": 5})

    def refuse(r):
        raise httpx.ConnectError("down")

    _use_supabase(monkeypatch, refuse)
    metrics.record_request({"total_ms": 5})


def test_summarize_and_rows_from_supabase(monkeypatch):
    fake = [{"record": {"total_ms": 100, "cost_usd": 0.5}}, {"record": {"total_ms": 300, "refused": True}}]
    calls = _use_supabase(monkeypatch, lambda r: httpx.Response(200, json=fake))
    assert metrics.metrics_rows() == [fake[0]["record"], fake[1]["record"]]
    params = calls[0].url.params
    assert params["select"] == "record" and params["order"] == "created_at.desc" and params["limit"]
    s = metrics.summarize()
    assert s["requests"] == 2 and s["refusal_rate"] == 0.5 and s["cost_usd_total"] == 0.5
    assert s["latency_ms"]["p50"] == 300


def test_file_rows_newest_first(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "vector_store", "chroma")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    assert metrics.metrics_rows() == []
    metrics.record_request({"n": 1})
    metrics.record_request({"n": 2})
    assert [r["n"] for r in metrics.metrics_rows()] == [2, 1]


def _fake_pipeline(monkeypatch, delays=None):
    asked = []

    def ask(question, ticker, llm_provider=None):
        asked.append(question)
        time.sleep(delays[question] if delays else 0)
        return AnswerResult(answer=f"ans {question}", sources=[], prompt_version="v", contexts=[])

    llm = SimpleNamespace(invoke=lambda msgs: SimpleNamespace(content="synth", usage_metadata={}))
    monkeypatch.setattr(thesis, "ask", ask)
    monkeypatch.setattr(thesis, "get_llm", lambda p=None: llm)
    monkeypatch.setattr(thesis, "build_factor_report", lambda t: FactorReport(ticker=t, cik=1))
    monkeypatch.setattr(thesis, "_corpus_fingerprint", lambda t: "fp1")
    monkeypatch.setattr(thesis, "record_request", lambda r: None)
    return asked


def test_thesis_cache_round_trip_on_supabase(monkeypatch):
    rows: dict[str, dict] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            body = json.loads(req.content)
            rows[body["ticker"]] = body
            return httpx.Response(201)
        ticker = req.url.params["ticker"].removeprefix("eq.")
        return httpx.Response(200, json=[{"payload": rows[ticker]["payload"]}] if ticker in rows else [])

    calls = _use_supabase(monkeypatch, handler)
    asked = _fake_pipeline(monkeypatch)

    first = thesis.build_thesis("aapl")
    n_asked = len(asked)
    second = thesis.build_thesis("AAPL")

    assert len(asked) == n_asked == len(thesis.THESIS_QUESTIONS)  # second call served from cache
    assert second == first
    upsert = next(c for c in calls if c.method == "POST")
    assert upsert.url.params["on_conflict"] == "ticker"
    assert "resolution=merge-duplicates" in upsert.headers["Prefer"]
    assert rows["AAPL"]["fingerprint"] == "fp1"

    # stale fingerprint or prompt_version -> recompute
    monkeypatch.setattr(thesis, "_corpus_fingerprint", lambda t: "fp2")
    thesis.build_thesis("AAPL")
    assert len(asked) == 2 * n_asked


def test_thesis_cache_failures_fall_back_to_recompute(monkeypatch):
    _use_supabase(monkeypatch, lambda r: httpx.Response(500, json={"message": "boom"}))
    asked = _fake_pipeline(monkeypatch)
    result = thesis.build_thesis("AAPL")
    assert result.synthesis == "synth" and len(asked) == len(thesis.THESIS_QUESTIONS)


def test_thesis_sections_keep_order_when_asks_finish_in_reverse(monkeypatch):
    monkeypatch.setattr(settings, "vector_store", "chroma")
    monkeypatch.setattr(thesis, "_load_cached", lambda t, f: None)
    monkeypatch.setattr(thesis, "_save_cache", lambda r, f: None)
    qs = [q for _, q in thesis.THESIS_QUESTIONS]
    _fake_pipeline(monkeypatch, delays={q: 0.1 * (len(qs) - i) for i, q in enumerate(qs)})
    result = thesis.build_thesis("AAPL")
    assert [s.topic for s in result.sections] == [t for t, _ in thesis.THESIS_QUESTIONS]
