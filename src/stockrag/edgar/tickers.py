from stockrag.config import settings
from stockrag.edgar.client import EdgarClient

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def load_ticker_map(client: EdgarClient) -> dict[str, int]:
    cache_path = settings.data_dir / "company_tickers.json"
    raw = client.get_json(TICKERS_URL, cache_path=cache_path)
    return {entry["ticker"].upper(): entry["cik_str"] for entry in raw.values()}


def cik_for_ticker(ticker: str, client: EdgarClient | None = None) -> int:
    owns_client = client is None
    client = client or EdgarClient()
    try:
        mapping = load_ticker_map(client)
        cik = mapping.get(ticker.upper())
        if cik is None:
            raise ValueError(f"Unknown ticker: {ticker}")
        return cik
    finally:
        if owns_client:
            client.close()
