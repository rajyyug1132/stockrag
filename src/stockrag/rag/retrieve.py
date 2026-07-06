from functools import lru_cache

from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from stockrag.rag.store import get_vector_store

CANDIDATES_PER_RETRIEVER = 30


def _ticker_documents(ticker: str) -> list[Document]:
    store = get_vector_store()
    raw = store._collection.get(where={"ticker": ticker.upper()}, include=["documents", "metadatas"])
    return [
        Document(page_content=text, metadata=meta)
        for text, meta in zip(raw["documents"], raw["metadatas"])
    ]


@lru_cache(maxsize=8)
def _bm25_retriever(ticker: str) -> BM25Retriever | None:
    """In-memory BM25 over a ticker's ingested chunks; rebuilt per process,
    which is fine at this corpus size. ``None`` when nothing is ingested.

    NOTE: cached per ticker, so a process that ingests new filings should not
    reuse a previously cached retriever (the CLI never does; the API would
    need a cache clear on ingest, added when that becomes a real workflow).
    """
    docs = _ticker_documents(ticker.upper())
    if not docs:
        return None
    retriever = BM25Retriever.from_documents(docs)
    retriever.k = CANDIDATES_PER_RETRIEVER
    return retriever


def get_hybrid_retriever(ticker: str) -> BaseRetriever:
    """BM25 + vector search fused with Reciprocal Rank Fusion (LangChain's
    EnsembleRetriever uses RRF internally). Falls back to pure vector search
    when BM25 has no corpus yet.
    """
    store = get_vector_store()
    vector_retriever = store.as_retriever(
        search_kwargs={"k": CANDIDATES_PER_RETRIEVER, "filter": {"ticker": ticker.upper()}}
    )
    bm25 = _bm25_retriever(ticker.upper())
    if bm25 is None:
        return vector_retriever
    return EnsembleRetriever(retrievers=[bm25, vector_retriever], weights=[0.5, 0.5])
