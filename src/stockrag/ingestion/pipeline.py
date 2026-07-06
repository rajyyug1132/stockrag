from dataclasses import dataclass

from stockrag.edgar.client import EdgarClient
from stockrag.edgar.filings import FilingRef, download_filing, list_filings
from stockrag.edgar.tickers import cik_for_ticker
from stockrag.ingestion.chunk import chunk_text
from stockrag.ingestion.parse import parse_filing_sections
from stockrag.rag.store import accession_already_ingested, get_vector_store


@dataclass(frozen=True)
class IngestResult:
    filings_ingested: int
    filings_skipped: int
    chunks_added: int


def _chunk_filing(ref: FilingRef, html: str) -> tuple[list[str], list[dict]]:
    texts: list[str] = []
    metadatas: list[dict] = []
    for section in parse_filing_sections(html):
        for chunk in chunk_text(section.text, section.name):
            texts.append(chunk.text)
            metadatas.append(
                {
                    "ticker": ref.ticker,
                    "form": ref.form,
                    "filing_date": ref.filing_date,
                    "accession": ref.accession_number,
                    "section": chunk.section,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                }
            )
    return texts, metadatas


def ingest_html(
    html: str,
    ticker: str,
    form: str = "10-K",
    filing_date: str = "",
    accession: str = "local",
) -> IngestResult:
    """Ingest a filing from local HTML without touching EDGAR — used by the
    CI eval workflow (fixtures only, no network) and for ad-hoc documents.
    """
    store = get_vector_store()
    if accession_already_ingested(store, accession):
        return IngestResult(filings_ingested=0, filings_skipped=1, chunks_added=0)

    ref = FilingRef(
        ticker=ticker.upper(),
        cik=0,
        accession_number=accession,
        form=form,
        filing_date=filing_date,
        primary_document="local.html",
    )
    texts, metadatas = _chunk_filing(ref, html)
    if texts:
        ids = [f"{accession}:{i}" for i in range(len(texts))]
        store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    return IngestResult(filings_ingested=1, filings_skipped=0, chunks_added=len(texts))


def ingest_ticker(ticker: str, forms: tuple[str, ...] = ("10-K",), years: int = 2) -> IngestResult:
    store = get_vector_store()

    with EdgarClient() as client:
        cik = cik_for_ticker(ticker, client=client)
        filings = list_filings(ticker, cik, client, forms=forms, years=years)

        filings_ingested = 0
        filings_skipped = 0
        chunks_added = 0

        for ref in filings:
            if accession_already_ingested(store, ref.accession_number):
                filings_skipped += 1
                continue

            html = download_filing(ref, client)
            texts, metadatas = _chunk_filing(ref, html)
            if texts:
                ids = [f"{ref.accession_number}:{i}" for i in range(len(texts))]
                store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
                chunks_added += len(texts)
            filings_ingested += 1

    return IngestResult(
        filings_ingested=filings_ingested,
        filings_skipped=filings_skipped,
        chunks_added=chunks_added,
    )
