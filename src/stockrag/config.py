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

    llm_provider: str = "nvidia"  # "nvidia" (NIM API), "gemini" (API), or "ollama" (local)
    ollama_model: str = "qwen3:4b"  # fits ~5GB free RAM; qwen3:14b needs 8.4GB
    gemini_model: str = "gemini-3.5-flash"  # 2.5-flash is 404 for new API keys

    # NVIDIA NIM (OpenAI-compatible); free endpoint, no daily-20 cap like Gemini free tier.
    nvidia_api_key: str = ""
    # Generation: nemotron-super cites reliably (~3-10s/answer). Judge: Ragas fires
    # ~4 long prompts per question; nemotron-super ran 8-100s/call under CI load →
    # mass judge timeouts, while mistral-nemotron answers judge prompts in ~1s.
    nvidia_model: str = "nvidia/llama-3.3-nemotron-super-49b-v1.5"
    # mistral-nemotron: ~1s/call. Earlier verdict swings (faithfulness 0.86 ->
    # 0.375 same input) were the judge running at temperature 0.2, not the
    # model — run_eval now pins the judge to temperature 0.0.
    nvidia_judge_model: str = "mistralai/mistral-nemotron"
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

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.filings_dir, self.facts_dir, self.chroma_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
