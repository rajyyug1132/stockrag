from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings

from stockrag.config import settings

# bge models expect an instruction prefix on queries but NOT on the
# documents being indexed.
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class BgeEmbeddings(Embeddings):
    def __init__(self, model_name: str):
        self._inner = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._inner.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_query(QUERY_INSTRUCTION + text)


@lru_cache(maxsize=1)
def get_embeddings() -> BgeEmbeddings:
    return BgeEmbeddings(settings.embedding_model)
