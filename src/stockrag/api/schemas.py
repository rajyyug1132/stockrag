from pydantic import BaseModel


class IngestResponse(BaseModel):
    ticker: str
    filings_ingested: int
    filings_skipped: int
    chunks_added: int


class AskRequest(BaseModel):
    question: str
    ticker: str
    llm: str | None = None  # "ollama" (default) or "gemini"


class SourceOut(BaseModel):
    index: int
    form: str
    filing_date: str
    section: str
    accession: str


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    prompt_version: str
