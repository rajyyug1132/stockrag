import logging
from collections.abc import Sequence
from functools import lru_cache

import httpx
from langchain_core.callbacks import CallbackManagerForRetrieverRun, Callbacks
from langchain_core.documents import BaseDocumentCompressor, Document
from langchain_core.retrievers import BaseRetriever

from stockrag.config import settings

logger = logging.getLogger("uvicorn.error")

RERANK_TOP_N = 6


@lru_cache(maxsize=1)
def _cross_encoder():
    # Imported here: sentence-transformers/torch are absent from the slim
    # (serverless) install, and langchain.retrievers drags in transformers.
    from langchain_community.cross_encoders import HuggingFaceCrossEncoder

    return HuggingFaceCrossEncoder(model_name=settings.reranker_model)


def _local_reranker(top_n: int) -> BaseDocumentCompressor:
    from langchain.retrievers.document_compressors import CrossEncoderReranker

    return CrossEncoderReranker(model=_cross_encoder(), top_n=top_n)


class NvidiaReranker(BaseDocumentCompressor):
    """Hosted NIM reranker (nemotron-3.5-rerank-8b by default). Any failure
    (missing key, timeout, 4xx/5xx, odd payload) logs a warning and falls back
    to the local cross-encoder, so a flaky free endpoint can't break a question.
    Without a local cross-encoder installed it keeps the retriever's fused order."""

    top_n: int = RERANK_TOP_N
    timeout_s: float = 30.0

    def _rank(self, query: str, documents: Sequence[Document]) -> list[int]:
        if not settings.nvidia_api_key:
            raise RuntimeError("NVIDIA_API_KEY is not set")
        resp = httpx.post(
            settings.nvidia_rerank_url,
            headers={"Authorization": f"Bearer {settings.nvidia_api_key}", "Accept": "application/json"},
            json={
                "model": settings.nvidia_rerank_model,
                "query": {"text": query},
                "passages": [{"text": d.page_content} for d in documents],
                "truncate": "END",
            },
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        rankings = resp.json()["rankings"]
        rankings = sorted(rankings, key=lambda r: r["logit"], reverse=True)
        return [r["index"] for r in rankings]

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Callbacks | None = None,
    ) -> Sequence[Document]:
        if not documents:
            return []
        try:
            order = self._rank(query, documents)
        except Exception as exc:
            logger.warning("NVIDIA rerank failed (%s: %s); falling back to local cross-encoder",
                           type(exc).__name__, exc)
            try:
                local = _local_reranker(self.top_n)
            except ImportError as imp:
                logger.warning("local cross-encoder unavailable (%s); keeping fused retrieval order", imp)
                return list(documents)[: self.top_n]
            return local.compress_documents(documents, query, callbacks)
        return [documents[i] for i in order[: self.top_n]]


class RerankingRetriever(BaseRetriever):
    """Base retriever's candidates, rescored by the compressor. Same contract
    as LangChain's ContextualCompressionRetriever, without importing
    langchain.retrievers (which loads transformers/torch when installed)."""

    base_retriever: BaseRetriever
    base_compressor: BaseDocumentCompressor

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        docs = self.base_retriever.invoke(query, config={"callbacks": run_manager.get_child()})
        if not docs:
            return []
        return list(self.base_compressor.compress_documents(docs, query, callbacks=run_manager.get_child()))


def with_reranker(base_retriever: BaseRetriever, top_n: int = RERANK_TOP_N) -> BaseRetriever:
    """Rescore the base retriever's candidates and keep only the top_n
    highest-quality chunks for the LLM. RERANKER_PROVIDER picks the scorer:
    "local" (default, cross-encoder) or "nvidia" (hosted NIM, local fallback).
    """
    if settings.reranker_provider == "nvidia":
        compressor: BaseDocumentCompressor = NvidiaReranker(top_n=top_n)
    else:
        compressor = _local_reranker(top_n)
    return RerankingRetriever(base_retriever=base_retriever, base_compressor=compressor)
