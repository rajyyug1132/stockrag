import json
import logging
import os
import tempfile
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

from stockrag.api.docs import DOCS_HTML
from stockrag.config import settings
from stockrag.api.schemas import (
    AskRequest,
    AskResponse,
    IngestResponse,
    SourceOut,
    ThesisResponse,
    ThesisSectionOut,
)
from stockrag.factor_engine.report import FactorReport, build_factor_report
from stockrag.ingestion.pipeline import ingest_pdf, ingest_ticker
from stockrag.rag.answer import AnswerResult, ask as rag_ask, ask_stream as rag_ask_stream
from stockrag.rag.metrics import metrics_path
from stockrag.rag.thesis import build_thesis

# uvicorn only attaches handlers to its own loggers, so a module logger's INFO
# lines would never reach the server log (e.g. the Space's boot log).
logger = logging.getLogger("uvicorn.error")

# Set by the lifespan when AUTO_INGEST_TICKERS is non-empty; tests can join it.
auto_ingest_thread: threading.Thread | None = None


def _parse_tickers(raw: str) -> list[str]:
    """Comma-separated tickers -> stripped, upper-cased, de-duplicated, order kept."""
    seen: dict[str, None] = {}
    for part in raw.split(","):
        ticker = part.strip().upper()
        if ticker:
            seen.setdefault(ticker)
    return list(seen)


def _auto_ingest(tickers: list[str]) -> None:
    for ticker in tickers:
        logger.info("auto-ingest: starting %s", ticker)
        try:
            result = ingest_ticker(ticker)
        except Exception:
            logger.exception("auto-ingest: %s failed", ticker)
            continue
        logger.info(
            "auto-ingest: finished %s (filings_ingested=%d, chunks_added=%d)",
            ticker,
            result.filings_ingested,
            result.chunks_added,
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global auto_ingest_thread
    auto_ingest_thread = None
    tickers = _parse_tickers(settings.auto_ingest_tickers)
    if tickers:
        auto_ingest_thread = threading.Thread(
            target=_auto_ingest, args=(tickers,), name="auto-ingest", daemon=True
        )
        auto_ingest_thread.start()
    yield


app = FastAPI(title="StockRAG", docs_url=None, lifespan=lifespan)

# Frontend is deployed on a different origin (Vercel) than the API (HF Spaces).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/docs", include_in_schema=False)
def custom_docs() -> HTMLResponse:
    return HTMLResponse(DOCS_HTML)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def get_metrics() -> list[dict]:
    """Recorded ask() requests, newest first (backs the frontend Metrics view)."""
    path = metrics_path()
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[::-1]


@app.get("/factors/{ticker}")
def get_factors(ticker: str) -> FactorReport:
    try:
        return build_factor_report(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _check_ingest_token(token: str) -> None:
    if settings.ingest_token and token != settings.ingest_token:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Ingest-Token header.")


@app.post("/ingest/{ticker}")
def ingest(
    ticker: str,
    forms: str = "10-K",
    years: int = 2,
    x_ingest_token: str = Header(default=""),
) -> IngestResponse:
    _check_ingest_token(x_ingest_token)
    form_tuple = tuple(f.strip() for f in forms.split(","))
    try:
        result = ingest_ticker(ticker, forms=form_tuple, years=years)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return IngestResponse(ticker=ticker.upper(), **result.__dict__)


@app.post("/ingest-pdf")
def ingest_pdf_endpoint(
    ticker: str = Form(...),
    filing_date: str = Form(default=""),
    file: UploadFile = File(...),
    x_ingest_token: str = Header(default=""),
) -> IngestResponse:
    """Ingest an uploaded Indian annual-report PDF (deployed Space has no
    local files to point ingest_pdf at)."""
    _check_ingest_token(x_ingest_token)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        result = ingest_pdf(tmp_path, ticker, filing_date=filing_date)
    finally:
        os.unlink(tmp_path)
    return IngestResponse(ticker=ticker.upper(), **result.__dict__)


@app.get("/thesis/{ticker}")
def get_thesis(ticker: str, llm: str | None = None) -> ThesisResponse:
    """Evidence briefing: factor report + filing evidence, synthesized.
    Slow (several LLM calls); ingest the ticker first."""
    try:
        result = build_thesis(ticker, llm_provider=llm)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ThesisResponse(
        ticker=result.ticker,
        synthesis=result.synthesis,
        sections=[
            ThesisSectionOut(
                topic=s.topic,
                question=s.question,
                answer=s.result.answer,
                grounding=s.grounding,
                sources=[SourceOut(**src.__dict__) for src in s.result.sources],
            )
            for s in result.sections
        ],
        prompt_version=result.prompt_version,
    )


@app.post("/ask/stream")
def ask_stream_endpoint(request: AskRequest) -> StreamingResponse:
    """SSE stream: {"token": str} events as the answer generates, then one
    {"done": true, answer, sources, prompt_version} event with the validated
    final answer (citation gate applied) that the client must render instead.
    A failure after headers are sent becomes one {"error": str} event, since
    the 200 status can no longer change."""

    def gen():
        try:
            for item in rag_ask_stream(request.question, request.ticker, llm_provider=request.llm):
                if isinstance(item, AnswerResult):
                    payload = {
                        "done": True,
                        "answer": item.answer,
                        "sources": [s.__dict__ for s in item.sources],
                        "prompt_version": item.prompt_version,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                else:
                    yield f"data: {json.dumps({'token': item})}\n\n"
        except Exception as exc:
            logger.exception("ask/stream failed for %s", request.ticker)
            yield f"data: {json.dumps({'error': f'{type(exc).__name__}: {exc}'})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/ask")
def ask_endpoint(request: AskRequest) -> AskResponse:
    result = rag_ask(request.question, request.ticker, llm_provider=request.llm)
    return AskResponse(
        answer=result.answer,
        sources=[SourceOut(**s.__dict__) for s in result.sources],
        prompt_version=result.prompt_version,
    )
