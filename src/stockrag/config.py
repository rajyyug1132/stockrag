from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    sec_user_agent: str = "StockRAG/0.1 rajyyug@gmail.com"

    # Langfuse tracing (optional; tracing is a no-op when keys are absent).
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # Everything written at runtime lives under data_dir; on a read-only
    # serverless filesystem set DATA_DIR to a writable temp dir (/tmp/stockrag).
    data_dir: Path = PROJECT_ROOT / "data"
    # Inside the package so a non-editable install (the Vercel API) ships them.
    prompts_dir: Path = Path(__file__).parent / "prompts"

    @property
    def filings_dir(self) -> Path:
        return self.data_dir / "filings"

    @property
    def facts_dir(self) -> Path:
        return self.data_dir / "facts"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    # Retrieval backend: "chroma" (local disk + in-process BM25, the default
    # for dev, Ollama and CI) or "supabase" (pgvector + Postgres full-text,
    # for the serverless API). The service key is server-side only.
    vector_store: str = "chroma"
    supabase_url: str = ""
    supabase_service_key: str = ""

    # Embeddings: "local" (bge below, on CPU) or "nvidia" (hosted NIM). Vectors
    # from the two are not interchangeable: an index built with one must be
    # queried with the same one.
    embedding_provider: str = "local"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # Confirmed 2026-11-15 (scripts/probe_nim_embed.py --confirm): 1024-d via the
    # `dimensions` parameter, 650- and 1300-token passages untruncated, ~0.6s.
    # llama-3.2-nv-embedqa-1b-v2, llama-nemotron-embed-1b-v2 and baai/bge-m3
    # are retired (410 Gone).
    nvidia_embed_model: str = "nvidia/nemotron-3.5-embed-1b"
    nvidia_embed_url: str = "https://integrate.api.nvidia.com/v1/embeddings"
    # Vector size requested from nvidia_embed_model; must equal vector(N) in
    # supabase/migrations (tests/test_migrations.py). 1024 stays under
    # pgvector's 2000-dim limit for HNSW/ivfflat should an index be needed.
    nvidia_embed_dim: int = 1024
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # "local" (cross-encoder above) or "nvidia" (hosted NIM reranker, uses
    # NVIDIA_API_KEY; falls back to local on any error). Default stays local
    # so CI and offline runs never hit the network.
    reranker_provider: str = "local"
    nvidia_rerank_model: str = "nvidia/nemotron-3.5-rerank-8b"
    nvidia_rerank_url: str = (
        "https://ai.api.nvidia.com/v1/retrieval/nvidia/nemotron-3.5-rerank-8b/reranking"
    )

    llm_provider: str = "nvidia"  # "nvidia" (NIM API), "gemini" (API), or "ollama" (local)
    ollama_model: str = "qwen3:4b"  # fits ~5GB free RAM; qwen3:14b needs 8.4GB
    # Token budget for retrieved context sent to Ollama. Must leave room inside
    # num_ctx (8192, rag/llm.py) for the rules, the question and the answer;
    # counted with cl100k, which undercounts qwen's tokenizer a little.
    ollama_context_tokens: int = 5500
    gemini_model: str = "gemini-3.5-flash"  # 2.5-flash is 404 for new API keys

    # NVIDIA NIM (OpenAI-compatible); free endpoint, no daily-20 cap like Gemini free tier.
    nvidia_api_key: str = ""
    # Generation: minimax-m3.1-flash cites per claim (smoke citation_coverage
    # 0.86, ~4s/answer warm). Replaced llama-3.3-nemotron-super-49b-v1.5, which
    # NVIDIA retired 2026-08-26 (410 Gone). nemotron-3.5-lightning-30b-a3b is
    # faster but cited at paragraph end (coverage 0.70); several other listed
    # models (nemotron-3-super-120b, nemotron-nano-3, mistral-large-2) 404 on
    # invoke for this account.
    nvidia_model: str = "minimaxai/minimax-m3.1-flash"
    # Judge: mistral-nemotron was retired 2026-09-28 (410). lightning answers in
    # <1s per call but hasn't been validated as a Ragas judge yet (open TODO).
    # run_eval pins the judge to temperature 0.0; verdict swings at 0.2 were the
    # temperature, not the model.
    nvidia_judge_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    chunk_tokens: int = 650
    chunk_overlap_tokens: int = 100
    # Small-to-big retrieval: widen each reranked chunk by N section neighbours
    # on each side before sending to the LLM. 0 disables; raise if answers lack
    # surrounding context, lower if the prompt gets too long.
    parent_window: int = 1

    edgar_requests_per_second: float = 8.0

    # When set, POST /ingest requires a matching X-Ingest-Token header —
    # a public /ingest lets strangers burn LLM quota and hit EDGAR from the
    # server's IP. Empty (default) leaves it open for local dev.
    ingest_token: str = ""

    # Comma-separated tickers (e.g. "AAPL,MSFT") ingested in a background thread
    # at API startup — for hosts with an ephemeral disk. Empty (default) = off.
    auto_ingest_tickers: str = ""

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.filings_dir, self.facts_dir, self.chroma_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
