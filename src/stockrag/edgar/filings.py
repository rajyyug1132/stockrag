from dataclasses import dataclass
from datetime import date

from stockrag.config import settings
from stockrag.edgar.client import EdgarClient


@dataclass(frozen=True)
class FilingRef:
    ticker: str
    cik: int
    accession_number: str  # e.g. "0000320193-24-000123"
    form: str
    filing_date: str
    primary_document: str

    @property
    def accession_nodash(self) -> str:
        return self.accession_number.replace("-", "")

    @property
    def document_url(self) -> str:
        return (
            f"https://www.sec.gov/Archives/edgar/data/{self.cik}/"
            f"{self.accession_nodash}/{self.primary_document}"
        )


def submissions_url(cik: int) -> str:
    return f"https://data.sec.gov/submissions/CIK{cik:010d}.json"


def list_filings(
    ticker: str,
    cik: int,
    client: EdgarClient,
    forms: tuple[str, ...] = ("10-K",),
    years: int = 2,
) -> list[FilingRef]:
    """List recent filings of the given forms within the last `years` years.

    Uses the submissions API's "recent" window, which comfortably covers a
    few years of 10-K/10-Q history for any active filer.
    """
    cache_path = settings.data_dir / f"submissions_CIK{cik:010d}.json"
    data = client.get_json(submissions_url(cik), cache_path=cache_path)
    recent = data.get("filings", {}).get("recent", {})

    today = date.today()
    cutoff = today.replace(year=today.year - years)

    refs: list[FilingRef] = []
    forms_list = recent.get("form", [])
    for i in range(len(forms_list)):
        form = forms_list[i]
        if form not in forms:
            continue
        filing_date_str = recent["filingDate"][i]
        if date.fromisoformat(filing_date_str) < cutoff:
            continue
        refs.append(
            FilingRef(
                ticker=ticker.upper(),
                cik=cik,
                accession_number=recent["accessionNumber"][i],
                form=form,
                filing_date=filing_date_str,
                primary_document=recent["primaryDocument"][i],
            )
        )
    return refs


def download_filing(ref: FilingRef, client: EdgarClient) -> str:
    cache_path = settings.filings_dir / ref.ticker / f"{ref.accession_nodash}.html"
    return client.get_text(ref.document_url, cache_path=cache_path)
