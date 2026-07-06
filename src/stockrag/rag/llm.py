from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from stockrag.config import settings


@lru_cache(maxsize=4)
def get_llm(provider: str | None = None) -> BaseChatModel:
    """Local-first LLM: Ollama by default, Gemini as opt-in fallback
    (``provider="gemini"``, used for eval judging and when quality/speed
    matters more than staying offline).
    """
    provider = provider or settings.llm_provider
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        # reasoning=False: qwen3 is a thinking model; without this it wastes
        # CPU minutes on <think> blocks before the cited answer.
        # num_ctx: Ollama defaults to a 4096-token window, which silently
        # truncates our ~5k-token RAG prompt (question first = question lost).
        return ChatOllama(
            model=settings.ollama_model,
            temperature=0.2,
            reasoning=False,
            num_ctx=8192,
        )
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            temperature=0.2,
            google_api_key=settings.gemini_api_key,
        )
    raise ValueError(f"Unknown LLM provider: {provider!r} (expected 'ollama' or 'gemini')")
