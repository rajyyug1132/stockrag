import json
import logging
import os
import secrets
import tempfile
import threading
import time
from collections import deque
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Path, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from stockrag.api.docs import DOCS_HTML
from stockrag.config import settings
from stockrag.api.schemas import (
    AskRequest,
    AskResponse,
    TICKER_PATTERN,
    IngestResponse,
    SourceOut,
    ThesisResponse,
    ThesisSectionOut,
)
from stockrag.factor_engine.report import FactorReport, build_factor_report
from stockrag.ingestion.pipeline import ingest_pdf, ingest_ticker
from stockrag.rag.answer import AnswerResult, ask as rag_ask, ask_stream as rag_ask_stream
from stockrag.rag.metrics import metrics_rows
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


Ticker = Path(pattern=TICKER_PATTERN)

# ponytail: in-memory window is per instance — serverless instances and
# restarts don't share it, so the real ceiling is limit x instances. Upgrade
# path: a shared counter (Upstash Redis, or a Postgres table in Supabase).
_hits: dict[str, deque[float]] = {}
_hits_lock = threading.Lock()


def rate_limit(request: Request) -> None:
    """Sliding 60s window per client IP; 429 + Retry-After when exceeded."""
    limit = settings.rate_limit_per_minute
    if limit <= 0:
        return
    header = settings.client_ip_header
    # Rightmost entry: the one the host's proxy appended. Leftmost entries of
    # an appended X-Forwarded-For are whatever the client sent.
    # getlist: a proxy may add its own header line rather than append.
    ip = ",".join(request.headers.getlist(header)).split(",")[-1].strip() if header else ""
    ip = ip or (request.client.host if request.client else "unknown")
    now = time.monotonic()
    with _hits_lock:
        # ponytail: crude memory bound — 10k distinct IPs in a window resets
        # every bucket at once. IPv6 isn't grouped by /64 either; both go away
        # with the shared-counter upgrade above.
        if len(_hits) >= 10_000:
            _hits.clear()
        q = _hits.setdefault(ip, deque())
        while q and now - q[0] >= 60:
            q.popleft()
        if len(q) >= limit:
            retry_after = int(60 - (now - q[0])) + 1
            raise HTTPException(429, "Rate limit exceeded.", headers={"Retry-After": str(retry_after)})
        q.append(now)


def require_ingest_token(x_ingest_token: str = Header(default="")) -> None:
    expected = settings.ingest_token
    if not expected:
        # Fail closed unless explicitly opened for local dev: a typo in some
        # other setting must never make ingest public.
        if not settings.allow_open_ingest:
            raise HTTPException(status_code=503, detail="Ingest is disabled: INGEST_TOKEN is not set.")
        return
    if not secrets.compare_digest(x_ingest_token.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Invalid or missing X-Ingest-Token header.")


SMALL_BODY_BYTES = 64 * 1024  # /ask JSON is a 1000-char question


@app.middleware("http")
async def guard_body(request: Request, call_next):
    """Runs before FastAPI reads the body, so oversized, length-less or
    unauthenticated bodies are refused before they are buffered or spooled."""
    if request.method == "POST":
        is_ingest = request.url.path.startswith("/ingest")
        if "chunked" in request.headers.get("transfer-encoding", "").lower():
            # Size unknown until fully read; every client we serve sends a length.
            return JSONResponse({"detail": "Content-Length required."}, status_code=411)
        length = request.headers.get("content-length", "0")  # absent = no body
        if not length.isdigit():
            return JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)
        cap = (settings.max_upload_mb + 1) * 1024 * 1024 if is_ingest else SMALL_BODY_BYTES
        if int(length) > cap:
            return JSONResponse({"detail": "Request body too large."}, status_code=413)
        if is_ingest:
            try:
                rate_limit(request)  # throttles token guessing too
                require_ingest_token(request.headers.get("x-ingest-token", ""))
            except HTTPException as exc:
                return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    return await call_next(request)


# Added after the guard so it wraps it: the guard's 4xx responses still carry
# CORS headers and the browser sees the real status. Frontend is on Vercel.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


_thesis_slots = threading.BoundedSemaphore(max(1, settings.thesis_max_concurrent))


def _check_llm(llm: str | None) -> None:
    allowed = {p.strip() for p in settings.llm_providers.split(",") if p.strip()}
    if llm and llm not in allowed:
        raise HTTPException(status_code=422, detail=f"llm must be one of: {', '.join(sorted(allowed))}.")


@app.get("/docs", include_in_schema=False)
def custom_docs() -> HTMLResponse:
    return HTMLResponse(DOCS_HTML)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics", dependencies=[Depends(rate_limit), Depends(require_ingest_token)])
def get_metrics() -> list[dict]:
    """Recorded ask() requests, newest first (backs the frontend Metrics view)."""
    return metrics_rows()


@app.get("/factors/{ticker}", dependencies=[Depends(rate_limit)])
def get_factors(ticker: str = Ticker) -> FactorReport:
    try:
        return build_factor_report(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Unknown ticker.") from exc


@app.post("/ingest/{ticker}", dependencies=[Depends(require_ingest_token)])
def ingest(ticker: str = Ticker, forms: str = "10-K", years: int = 2) -> IngestResponse:
    form_tuple = tuple(f.strip() for f in forms.split(","))
    try:
        result = ingest_ticker(ticker, forms=form_tuple, years=years)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Unknown ticker.") from exc
    return IngestResponse(ticker=ticker.upper(), **result.__dict__)


@app.post("/ingest-pdf", dependencies=[Depends(require_ingest_token)])
def ingest_pdf_endpoint(
    ticker: str = Form(..., pattern=TICKER_PATTERN),
    filing_date: str = Form(default="", pattern=r"^(\d{4}-\d{2}-\d{2})?$"),
    file: UploadFile = File(...),
) -> IngestResponse:
    """Ingest an uploaded Indian annual-report PDF (deployed Space has no
    local files to point ingest_pdf at)."""
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"PDF larger than {settings.max_upload_mb} MB.")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        result = ingest_pdf(tmp_path, ticker, filing_date=filing_date)
    finally:
        os.unlink(tmp_path)
    return IngestResponse(ticker=ticker.upper(), **result.__dict__)


@app.get("/thesis/{ticker}", dependencies=[Depends(rate_limit)])
def get_thesis(ticker: str = Ticker, llm: str | None = None) -> ThesisResponse:
    """Evidence briefing: factor report + filing evidence, synthesized.
    Slow (several LLM calls); ingest the ticker first."""
    _check_llm(llm)
    if not _thesis_slots.acquire(blocking=False):
        raise HTTPException(429, "Thesis capacity busy, retry shortly.", headers={"Retry-After": "30"})
    try:
        result = build_thesis(ticker, llm_provider=llm)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Unknown ticker.") from exc
    finally:
        _thesis_slots.release()
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


@app.post("/ask/stream", dependencies=[Depends(rate_limit)])
def ask_stream_endpoint(request: AskRequest) -> StreamingResponse:
    """SSE stream: {"token": str} events as the answer generates, then one
    {"done": true, answer, sources, prompt_version} event with the validated
    final answer (citation gate applied) that the client must render instead.
    A failure after headers are sent becomes one {"error": str} event, since
    the 200 status can no longer change."""
    _check_llm(request.llm)

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
        except Exception:
            logger.exception("ask/stream failed for %s", request.ticker)
            yield f"data: {json.dumps({'error': 'Answer generation failed.'})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/ask", dependencies=[Depends(rate_limit)])
def ask_endpoint(request: AskRequest) -> AskResponse:
    _check_llm(request.llm)
    result = rag_ask(request.question, request.ticker, llm_provider=request.llm)
    return AskResponse(
        answer=result.answer,
        sources=[SourceOut(**s.__dict__) for s in result.sources],
        prompt_version=result.prompt_version,
    )
