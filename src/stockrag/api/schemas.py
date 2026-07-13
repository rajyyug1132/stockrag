from pydantic import BaseModel


class IngestResponse(BaseModel):
    ticker: str
    filings_ingested: int
    filings_skipped: int
    chunks_added: int


class AskRequest(BaseModel):
    question: str
    ticker: str
    llm: str | None = None  # "nvidia" (default), "gemini", or "ollama"; None = configured default


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


class ThesisSectionOut(BaseModel):
    topic: str
    question: str
    answer: str
    grounding: float
    sources: list[SourceOut]


class ThesisResponse(BaseModel):
    ticker: str
    synthesis: str
    sections: list[ThesisSectionOut]
    prompt_version: str
