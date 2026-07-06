from functools import lru_cache

from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_core.retrievers import BaseRetriever

from stockrag.config import settings

RERANK_TOP_N = 6


@lru_cache(maxsize=1)
def _cross_encoder() -> HuggingFaceCrossEncoder:
    return HuggingFaceCrossEncoder(model_name=settings.reranker_model)


def with_reranker(base_retriever: BaseRetriever, top_n: int = RERANK_TOP_N) -> BaseRetriever:
    """Rescore the base retriever's candidates with a local cross-encoder and
    keep only the top_n highest-quality chunks for the LLM.
    """
    compressor = CrossEncoderReranker(model=_cross_encoder(), top_n=top_n)
    return ContextualCompressionRetriever(base_compressor=compressor, base_retriever=base_retriever)
