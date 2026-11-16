"""Vector-store access. Ingestion and the thesis cache go through the small
`ChunkStore` interface (`get_store()`), so the backend can be Chroma (local,
default) or Supabase (hosted) without callers touching backend internals.
Chroma-only retrieval (BM25 corpus, vector-only A/B) still uses
`get_vector_store()` directly."""

from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

from stockrag.config import settings
from stockrag.rag.embed import get_embeddings

if TYPE_CHECKING:
    from langchain_chroma import Chroma

COLLECTION_NAME = "filings"


class ChunkStore(Protocol):
    def add_chunks(self, texts: list[str], metadatas: list[dict], ids: list[str]) -> None: ...

    def accession_ingested(self, accession: str) -> bool: ...

    def ticker_accessions(self, ticker: str) -> list[str]:
        """Sorted distinct accessions ingested for the ticker."""
        ...


@lru_cache(maxsize=1)
def get_vector_store() -> "Chroma":
    import chromadb
    from langchain_chroma import Chroma

    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return Chroma(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
    )


class ChromaStore:
    def __init__(self, chroma: "Chroma"):
        self.chroma = chroma

    def add_chunks(self, texts: list[str], metadatas: list[dict], ids: list[str]) -> None:
        self.chroma.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    def accession_ingested(self, accession: str) -> bool:
        return bool(self.chroma._collection.get(ids=[f"{accession}:0"])["ids"])

    def ticker_accessions(self, ticker: str) -> list[str]:
        # ponytail: pulls all chunk metadatas for the ticker; paginate if a
        # ticker ever holds >100k chunks.
        got = self.chroma._collection.get(where={"ticker": ticker}, include=["metadatas"])
        return sorted({m["accession"] for m in got["metadatas"]})


@lru_cache(maxsize=1)
def get_store() -> ChunkStore:
    if settings.vector_store == "chroma":
        return ChromaStore(get_vector_store())
    if settings.vector_store == "supabase":
        raise NotImplementedError("VECTOR_STORE=supabase lands in a later change")
    raise ValueError(f"VECTOR_STORE must be 'chroma' or 'supabase', got {settings.vector_store!r}")
