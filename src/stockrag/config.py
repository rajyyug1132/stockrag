from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    sec_user_agent: str = "StockRAG/0.1 rajyyug@gmail.com"

    data_dir: Path = PROJECT_ROOT / "data"
    filings_dir: Path = PROJECT_ROOT / "data" / "filings"
    facts_dir: Path = PROJECT_ROOT / "data" / "facts"
    chroma_dir: Path = PROJECT_ROOT / "data" / "chroma"
    prompts_dir: Path = PROJECT_ROOT / "prompts"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    llm_provider: str = "gemini"  # "gemini" (API, default for now) or "ollama" (local)
    ollama_model: str = "qwen3:4b"  # fits ~5GB free RAM; qwen3:14b needs 8.4GB
    gemini_model: str = "gemini-2.5-flash"

    chunk_tokens: int = 650
    chunk_overlap_tokens: int = 100

    edgar_requests_per_second: float = 8.0

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.filings_dir, self.facts_dir, self.chroma_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
