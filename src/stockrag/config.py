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

    data_dir: Path = PROJECT_ROOT / "data"
    filings_dir: Path = PROJECT_ROOT / "data" / "filings"
    facts_dir: Path = PROJECT_ROOT / "data" / "facts"
    chroma_dir: Path = PROJECT_ROOT / "data" / "chroma"
    prompts_dir: Path = PROJECT_ROOT / "prompts"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
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
