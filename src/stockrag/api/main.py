from fastapi import FastAPI, HTTPException

from stockrag.api.schemas import AskRequest, AskResponse, IngestResponse, SourceOut
from stockrag.factor_engine.report import FactorReport, build_factor_report
from stockrag.ingestion.pipeline import ingest_ticker
from stockrag.rag.answer import ask as rag_ask

app = FastAPI(title="StockRAG")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/factors/{ticker}")
def get_factors(ticker: str) -> FactorReport:
    try:
        return build_factor_report(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/ingest/{ticker}")
def ingest(ticker: str, forms: str = "10-K", years: int = 2) -> IngestResponse:
    form_tuple = tuple(f.strip() for f in forms.split(","))
    try:
        result = ingest_ticker(ticker, forms=form_tuple, years=years)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return IngestResponse(ticker=ticker.upper(), **result.__dict__)


@app.post("/ask")
def ask_endpoint(request: AskRequest) -> AskResponse:
    result = rag_ask(request.question, request.ticker, llm_provider=request.llm)
    return AskResponse(
        answer=result.answer,
        sources=[SourceOut(**s.__dict__) for s in result.sources],
        prompt_version=result.prompt_version,
    )
