import json
import time
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from stockrag.config import settings


class EdgarClient:
    """Rate-limited, disk-cached client for SEC EDGAR endpoints.

    EDGAR requires a descriptive User-Agent with a contact email and
    throttling well under its abuse-detection limits (see
    https://www.sec.gov/os/webmaster-faq#developers).
    """

    def __init__(self, user_agent: str | None = None, requests_per_second: float | None = None):
        self.user_agent = user_agent or settings.sec_user_agent
        rps = requests_per_second or settings.edgar_requests_per_second
        self._min_interval = 1.0 / rps
        self._last_request_at = 0.0
        self._client = httpx.Client(
            headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"},
            timeout=30.0,
        )

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_at = time.monotonic()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        reraise=True,
    )
    def _get(self, url: str) -> httpx.Response:
        self._throttle()
        response = self._client.get(url)
        response.raise_for_status()
        return response

    def get_json(self, url: str, cache_path: Path | None = None) -> dict:
        if cache_path and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))
        data = self._get(url).json()
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(data), encoding="utf-8")
        return data

    def get_text(self, url: str, cache_path: Path | None = None) -> str:
        if cache_path and cache_path.exists():
            return cache_path.read_text(encoding="utf-8", errors="ignore")
        text = self._get(url).text
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(text, encoding="utf-8")
        return text

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "EdgarClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
