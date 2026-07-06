from functools import lru_cache

import chromadb
from langchain_chroma import Chroma

from stockrag.config import settings
from stockrag.rag.embed import get_embeddings

COLLECTION_NAME = "filings"


@lru_cache(maxsize=1)
def get_vector_store() -> Chroma:
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return Chroma(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
    )


def accession_already_ingested(store: Chroma, accession_number: str) -> bool:
    existing = store._collection.get(ids=[f"{accession_number}:0"])
    return bool(existing["ids"])
