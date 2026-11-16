"""Supabase backend: chunks in Postgres (pgvector + full-text), reached over
PostgREST with httpx — no database driver, so the API stays a slim function.

Schema and SQL functions live in supabase/migrations. The service key is
server-side only; every table is RLS-locked to the service role.
"""

from functools import lru_cache
from typing import Any

import httpx
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from stockrag.config import settings

CANDIDATES = 30  # same candidate pool as the Chroma hybrid retriever
INSERT_BATCH = 100
CHUNK_COLUMNS = ("ticker", "form", "filing_date", "accession", "section", "chunk_index", "char_start", "char_end")


class SupabaseError(RuntimeError):
    pass


class SupabaseClient:
    """Minimal PostgREST client. Errors name the call and the server's message,
    never the key."""

    def __init__(self, url: str, key: str, client: httpx.Client | None = None, timeout_s: float = 15.0):
        # A pasted key often carries a trailing newline; an illegal header
        # value makes httpx echo the whole key in its error.
        url, key = url.strip(), key.strip()
        if not url or not key:
            raise SupabaseError("VECTOR_STORE=supabase needs SUPABASE_URL and SUPABASE_SERVICE_KEY")
        headers = {"apikey": key, "Content-Type": "application/json", "Accept": "application/json"}
        # Legacy service_role keys are JWTs and go in Authorization too; the
        # newer sb_secret_ keys are not JWTs and are sent as apikey only.
        if key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {key}"
        self._base = url.rstrip("/") + "/rest/v1"
        # Short keep-alive: a serverless instance thawed after minutes would
        # otherwise reuse sockets the server has already closed.
        self._http = client or httpx.Client(
            timeout=httpx.Timeout(timeout_s, connect=5.0), limits=httpx.Limits(keepalive_expiry=20.0)
        )
        self._headers = headers

    def request(self, method: str, path: str, *, retry: bool = False, **kwargs: Any) -> Any:
        """retry=True re-sends once after a transport error; only for calls
        that are safe to repeat (reads, RPCs, idempotent upserts)."""
        headers = {**self._headers, **kwargs.pop("headers", {})}
        resp, failure = None, ""
        for _ in range(2 if retry else 1):
            try:
                resp = self._http.request(method, f"{self._base}/{path}", headers=headers, **kwargs)
                break
            except httpx.TransportError as exc:
                # Keep the type only: some transport errors quote request
                # headers (the key). Raised below, outside the except block,
                # so the original isn't even chained as __context__.
                failure = type(exc).__name__
        if resp is None:
            raise SupabaseError(f"Supabase {method} {path}: {failure}")
        if resp.status_code >= 400:
            raise SupabaseError(f"Supabase {method} {path} -> HTTP {resp.status_code}: {_detail(resp)[:300]}")
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            raise SupabaseError(f"Supabase {method} {path}: non-JSON response ({resp.status_code})") from None

    def rpc(self, function: str, args: dict) -> Any:
        # Both RPCs are read-only (STABLE), so a retry is safe.
        return self.request("POST", f"rpc/{function}", json=args, retry=True)


def _detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text
    if isinstance(body, dict):
        return str(body.get("message") or body.get("msg") or body)
    return str(body)


@lru_cache(maxsize=1)
def get_client() -> SupabaseClient:
    return SupabaseClient(settings.supabase_url, settings.supabase_service_key)


def _embeddings() -> Embeddings:
    if settings.embedding_provider != "nvidia":
        # The chunks table holds vector(nvidia_embed_dim); local bge vectors
        # (384-d) would fail on insert and could never match on search.
        raise SupabaseError("VECTOR_STORE=supabase needs EMBEDDING_PROVIDER=nvidia")
    from stockrag.rag.embed import get_embeddings

    return get_embeddings()


class SupabaseStore:
    """ChunkStore over the `chunks` table."""

    def __init__(self, client: SupabaseClient | None = None, embeddings: Embeddings | None = None):
        self._client = client or get_client()
        self._embeddings = embeddings

    @property
    def embeddings(self) -> Embeddings:
        if self._embeddings is None:
            self._embeddings = _embeddings()
        return self._embeddings

    def add_chunks(self, texts: list[str], metadatas: list[dict], ids: list[str]) -> None:
        vectors = self.embeddings.embed_documents(texts)
        rows = [
            # Postgres text rejects NUL, which PDF extraction can produce.
            {"id": id_, "content": text.replace("\x00", ""), "embedding": vec, **{c: meta[c] for c in CHUNK_COLUMNS}}
            for id_, text, vec, meta in zip(ids, texts, vectors, metadatas, strict=True)
        ]
        # accession_ingested() keys on "{accession}:0", so that row goes in
        # last: a filing that fails half-way is retried, not silently skipped.
        rows = rows[1:] + rows[:1]
        for i in range(0, len(rows), INSERT_BATCH):
            self._client.request(
                "POST",
                "chunks",
                retry=True,  # upsert on id: repeating a batch is harmless
                params={"on_conflict": "id"},
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                json=rows[i : i + INSERT_BATCH],
            )

    def accession_ingested(self, accession: str) -> bool:
        found = self._client.request(
            "GET", "chunks", retry=True, params={"id": f"eq.{accession}:0", "select": "id"}
        )
        return bool(found)

    def ticker_accessions(self, ticker: str) -> list[str]:
        rows = self._client.rpc("ticker_accessions", {"p_ticker": ticker})
        # PostgREST returns a set of scalars either bare or keyed by function name.
        return sorted(r["ticker_accessions"] if isinstance(r, dict) else r for r in rows or [])


def _row_to_document(row: dict) -> Document:
    metadata = {c: row[c] for c in CHUNK_COLUMNS}
    metadata.update(score=row["score"], neighbours=row.get("neighbours") or [])
    return Document(page_content=row["content"], metadata=metadata)


class SupabaseRetriever(BaseRetriever):
    """hybrid_search RPC: vector + full-text legs fused with RRF in Postgres.
    page_content is the small chunk (what the reranker scores); its section
    neighbours ride along in metadata["neighbours"] for small-to-big widening."""

    ticker: str
    n: int = CANDIDATES
    window: int = 1
    # Injected in tests; kept out of repr so traces never print client state.
    client: Any = Field(default=None, repr=False)
    embeddings: Any = Field(default=None, repr=False)

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        embeddings = self.embeddings or _embeddings()
        client = self.client or get_client()
        rows = client.rpc(
            "hybrid_search",
            {
                "q": query,
                "q_embedding": embeddings.embed_query(query),
                "p_ticker": self.ticker.upper(),
                "n": self.n,
                "win": self.window,
            },
        )
        return [_row_to_document(r) for r in rows or []]
