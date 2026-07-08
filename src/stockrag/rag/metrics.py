import json
import re
from datetime import datetime, timezone
from pathlib import Path

from stockrag.config import settings

# USD per 1M tokens (input, output); absent/local models cost nothing.
MODEL_PRICES: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_CITATION_RE = re.compile(r"\[\d+\]")


def metrics_path() -> Path:
    return settings.data_dir / "metrics" / "requests.jsonl"


def citation_coverage(answer: str) -> float:
    """Fraction of substantive sentences carrying at least one [n] citation —
    the groundedness proxy we can compute without an LLM judge.
    """
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(answer) if len(s.strip()) > 20]
    if not sentences:
        return 0.0
    cited = sum(1 for s in sentences if _CITATION_RE.search(s))
    return cited / len(sentences)


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = MODEL_PRICES.get(model, (0.0, 0.0))
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def record_request(record: dict) -> None:
    """Append one request record to the JSONL metrics log. Never raises —
    metrics must not break the request path.
    """
    try:
        path = metrics_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), **record}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(int(len(ordered) * pct), len(ordered) - 1)
    return ordered[index]


def summarize() -> dict:
    path = metrics_path()
    if not path.exists():
        return {"requests": 0}

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    latencies = [r["total_ms"] for r in rows if "total_ms" in r]
    coverages = [r["citation_coverage"] for r in rows if "citation_coverage" in r]
    costs = [r["cost_usd"] for r in rows if "cost_usd" in r]
    refusals = [r for r in rows if r.get("refused")]
    errors = [r for r in rows if r.get("error")]

    return {
        "requests": len(rows),
        "latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
        },
        "retrieval_ms_p50": _percentile([r["retrieval_ms"] for r in rows if "retrieval_ms" in r], 0.50),
        "llm_ms_p50": _percentile([r["llm_ms"] for r in rows if "llm_ms" in r], 0.50),
        "citation_coverage_avg": sum(coverages) / len(coverages) if coverages else None,
        "refusal_rate": len(refusals) / len(rows) if rows else None,
        "error_rate": len(errors) / len(rows) if rows else None,
        "cost_usd_total": sum(costs),
        "cost_usd_per_request": sum(costs) / len(costs) if costs else None,
    }
