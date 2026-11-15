"""Probe NVIDIA NIM embedding models before picking one for the Supabase path.

Run from the repo root (it reads NVIDIA_API_KEY from .env there):

    uv run python scripts/probe_nim_embed.py

For every embedding model the account lists (plus a few known names), it
reports: does it answer, vector size, the largest passage it embeds without
truncation, whether `input_type` is required, and latency. A chunk is up to
650 cl100k tokens (CHUNK_TOKENS), so the pick must accept at least that.
Never prints the API key. Makes ~6 calls per model.

To confirm one model at a requested vector size instead (3 calls):

    uv run python scripts/probe_nim_embed.py --confirm nvidia/nemotron-3.5-embed-1b --dim 1024
"""

import json
import sys
import time

import httpx

from stockrag.config import PROJECT_ROOT, settings
from stockrag.ingestion.chunk import _ENCODING
from stockrag.ingestion.parse import parse_filing_sections

BASE = settings.nvidia_base_url.rstrip("/")
# Probed even if unlisted. llama-3.2-nv-embedqa-1b-v2, llama-nemotron-embed-1b-v2
# and baai/bge-m3 answer 410 Gone (retired) as of 2026-11-15.
KNOWN = [
    "nvidia/nemotron-3.5-embed-1b",
    "nvidia/nemotron-3.5-embed-8b",
    "nvidia/nv-embedqa-mistral-7b-v2",
    "snowflake/arctic-embed-l",
]
# cl100k token counts to try, smallest first; stop at the first failure.
SIZES = [settings.chunk_tokens, 1300, 4000, 8000]
PAUSE_S = 1.5  # stay under the free tier's per-minute limit
RETRY_PAUSE_S = 10.0


class ProbeError(Exception):
    def __init__(self, status: int | None, body: str):
        super().__init__(f"HTTP {status}: {body[:200]}" if status else body[:200])
        self.status = status
        self.body = body

    @property
    def rejects_input(self) -> bool:
        """A 4xx about the request itself (too long, bad field), not throttling."""
        return self.status in (400, 413, 422)


def _passage_tokens() -> list[int]:
    """Real 10-K text from the committed fixture, repeated to cover SIZES."""
    html = (PROJECT_ROOT / "tests" / "fixtures" / "aapl_10k_excerpt.html").read_text(encoding="utf-8")
    text = "\n\n".join(s.text for s in parse_filing_sections(html))
    tokens = _ENCODING.encode(text)
    if not tokens:
        raise SystemExit("fixture parsed to no text")
    while len(tokens) < max(SIZES):
        tokens = tokens + tokens
    return tokens


def _embed(
    client: httpx.Client,
    model: str,
    text: str,
    input_type: str | None,
    strict: bool = True,
    dimensions: int | None = None,
) -> tuple[list[float], float]:
    """One embedding call. strict sends truncate=NONE so an over-long input
    errors instead of being silently cut. A 429/5xx/timeout is retried once."""
    body: dict = {"model": model, "input": [text], "encoding_format": "float"}
    if dimensions:
        body["dimensions"] = dimensions
    if strict:
        body["truncate"] = "NONE"
    if input_type:
        body["input_type"] = input_type
    for attempt in range(2):
        started = time.perf_counter()
        try:
            resp = client.post(f"{BASE}/embeddings", json=body)
        except httpx.TransportError as exc:
            err = ProbeError(None, f"{type(exc).__name__}: {exc}")
        else:
            elapsed = time.perf_counter() - started
            time.sleep(PAUSE_S)
            if resp.status_code == 200:
                return resp.json()["data"][0]["embedding"], elapsed
            err = ProbeError(resp.status_code, resp.text)
            if not (resp.status_code == 429 or resp.status_code >= 500):
                raise err
        if attempt == 0:
            time.sleep(RETRY_PAUSE_S)
    raise err


def probe(client: httpx.Client, model: str, tokens: list[int]) -> dict:
    row: dict = {"model": model}
    passage = _ENCODING.decode(tokens[: settings.chunk_tokens])
    strict = True
    try:
        vec, secs = _embed(client, model, passage, "passage")
    except ProbeError as exc:
        if not (exc.rejects_input and "truncat" in exc.body.lower()):
            row.update(responds=False, error=str(exc))
            return row
        # The model rejects the truncate field itself: probe without it. Sizes
        # then only show what it accepts, not whether it silently truncates.
        strict = False
        try:
            vec, secs = _embed(client, model, passage, "passage", strict=False)
        except ProbeError as exc2:
            row.update(responds=False, error=str(exc2))
            return row
    row.update(responds=True, dim=len(vec), passage_650_s=round(secs, 2), truncate_none_supported=strict)

    # Sizes are cl100k tokens; each model counts in its own tokenizer, so
    # treat anything above 650 as approximate.
    row["max_ok_cl100k"] = settings.chunk_tokens
    for n in SIZES[1:]:
        try:
            _embed(client, model, _ENCODING.decode(tokens[:n]), "passage", strict=strict)
            row["max_ok_cl100k"] = n
        except ProbeError as exc:
            key = "first_fail_cl100k" if exc.rejects_input else "ladder_stopped_by_error_at"
            row[key] = n
            row["fail_error"] = str(exc)
            break

    try:
        qvec, secs = _embed(client, model, "What are Apple's main risk factors?", "query", strict=strict)
        row.update(query_ok=True, query_s=round(secs, 2), query_dim=len(qvec))
    except ProbeError as exc:
        row.update(query_ok=False, query_error=str(exc))

    try:
        _embed(client, model, passage, None, strict=strict)
        row["input_type_required"] = False
    except ProbeError as exc:
        if exc.rejects_input and "input_type" in exc.body.lower():
            row["input_type_required"] = True
        else:
            row["input_type_required"] = "unknown"
        row["no_input_type_error"] = str(exc)
    return row


def confirm(client: httpx.Client, model: str, dim: int, tokens: list[int]) -> bool:
    """Passage at the chunk size and at ~2x, plus a query, all at `dim`."""
    ok = True
    for label, text, input_type in (
        (f"passage {settings.chunk_tokens} cl100k", _ENCODING.decode(tokens[: settings.chunk_tokens]), "passage"),
        ("passage 1300 cl100k", _ENCODING.decode(tokens[:1300]), "passage"),
        ("query", "What are Apple's main risk factors?", "query"),
    ):
        try:
            vec, secs = _embed(client, model, text, input_type, dimensions=dim)
        except ProbeError as exc:
            print(f"FAIL {label}: {exc}")
            ok = False
            continue
        good = len(vec) == dim
        ok &= good
        print(f"{'OK  ' if good else 'FAIL'} {label}: {len(vec)}-d in {secs:.2f}s")
    return ok


def main() -> int:
    if not settings.nvidia_api_key:
        print("NVIDIA_API_KEY is not set: run this from the repo root, where .env lives.")
        return 1
    headers = {"Authorization": f"Bearer {settings.nvidia_api_key}", "Accept": "application/json"}
    if "--confirm" in sys.argv:
        model = sys.argv[sys.argv.index("--confirm") + 1]
        dim = int(sys.argv[sys.argv.index("--dim") + 1])
        with httpx.Client(headers=headers, timeout=60.0) as client:
            ok = confirm(client, model, dim, _passage_tokens())
        print(f"\n{model} at {dim} dimensions: {'ACCEPTED' if ok else 'NOT accepted'}")
        return 0 if ok else 1
    with httpx.Client(headers=headers, timeout=60.0) as client:
        resp = client.get(f"{BASE}/models")
        if resp.status_code != 200:
            print(f"Listing models failed: HTTP {resp.status_code}: {resp.text[:200]}")
            return 1
        listed = [m["id"] for m in resp.json()["data"]]
        candidates = sorted(
            {m for m in listed if "embed" in m.lower() or "bge" in m.lower()} | set(KNOWN)
        )
        print(f"{len(listed)} models listed; probing {len(candidates)} embedding candidates\n")
        tokens = _passage_tokens()
        rows = []
        for model in candidates:
            row = probe(client, model, tokens)
            row["listed"] = model in listed
            rows.append(row)
            if row["responds"]:
                print(
                    f"OK   {model}: dim={row['dim']} max_ok={row['max_ok_cl100k']} "
                    f"query_ok={row.get('query_ok')} input_type_required={row.get('input_type_required')} "
                    f"passage={row['passage_650_s']}s query={row.get('query_s')}s"
                )
            else:
                print(f"FAIL {model}: {row['error']}")

    print("\nJSON (paste this back):")
    print(json.dumps(rows, indent=1))
    usable = [r for r in rows if r["responds"] and r.get("query_ok")]
    if usable:
        print("\nAccept >= 650 tokens and answer queries:", ", ".join(r["model"] for r in usable))
    return 0


if __name__ == "__main__":
    sys.exit(main())
