from functools import lru_cache

import httpx
from langchain_core.embeddings import Embeddings
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from stockrag.config import settings

# bge models expect an instruction prefix on queries but NOT on the
# documents being indexed.
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class BgeEmbeddings(Embeddings):
    def __init__(self, model_name: str):
        # Imported here so the hosted (nvidia) path never loads torch.
        from langchain_huggingface import HuggingFaceEmbeddings

        self._inner = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._inner.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_query(QUERY_INSTRUCTION + text)


def _transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and (
        exc.response.status_code == 429 or exc.response.status_code >= 500
    )


class NvidiaEmbeddings(Embeddings):
    """Hosted NIM embeddings (OpenAI-compatible /embeddings). Retrieval models
    there embed queries and passages differently, selected by `input_type`."""

    def __init__(
        self,
        model: str,
        url: str,
        api_key: str,
        batch_size: int = 32,
        timeout_s: float = 60.0,
        client: httpx.Client | None = None,
    ):
        self.model = model
        self.url = url
        self.batch_size = batch_size
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=timeout_s)

    @retry(
        retry=retry_if_exception(_transient),
        stop=stop_after_attempt(5),
        # Free-tier 429s clear in tens of seconds: 4s, 8s, 16s, 30s.
        wait=wait_exponential(multiplier=2, min=4, max=30),
        reraise=True,
    )
    def _post(self, batch: list[str], input_type: str) -> list[list[float]]:
        if not self._api_key:
            raise RuntimeError("NVIDIA_API_KEY is not set (EMBEDDING_PROVIDER=nvidia)")
        resp = self._client.post(
            self.url,
            headers={"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"},
            json={
                "model": self.model,
                "input": batch,
                "input_type": input_type,
                "encoding_format": "float",
                # Chunks fit the model (see scripts/probe_nim_embed.py); END only
                # guards against tokenizer drift instead of failing an ingest.
                "truncate": "END",
            },
        )
        resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        if len(data) != len(batch):
            raise RuntimeError(f"NIM returned {len(data)} embeddings for {len(batch)} inputs")
        return [d["embedding"] for d in data]

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            out.extend(self._post(texts[i : i + self.batch_size], input_type))
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "passage")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "query")[0]


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
    if settings.embedding_provider == "nvidia":
        return NvidiaEmbeddings(
            model=settings.nvidia_embed_model,
            url=settings.nvidia_embed_url,
            api_key=settings.nvidia_api_key,
        )
    if settings.embedding_provider != "local":
        raise ValueError(f"EMBEDDING_PROVIDER must be 'local' or 'nvidia', got {settings.embedding_provider!r}")
    return BgeEmbeddings(settings.embedding_model)
