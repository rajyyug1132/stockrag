from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from stockrag.config import settings


@lru_cache(maxsize=8)
def get_llm(
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
) -> BaseChatModel:
    """Chat model for the given provider. ``model`` overrides that provider's
    configured default; ``temperature`` defaults to 0.2 for generation but the
    eval judge MUST pass 0.0 — a grader at 0.2 gives nondeterministic verdicts
    (same input scored faithfulness 0.86 then 0.375 across runs).
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
            temperature=temperature,
            reasoning=False,
            num_ctx=8192,
        )
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            temperature=temperature,
            google_api_key=settings.gemini_api_key,
        )
    if provider == "nvidia":
        from langchain_openai import ChatOpenAI

        # NIM is OpenAI-compatible. enable_thinking=False: nemotron reasoning models
        # otherwise put everything in reasoning_content and return empty content.
        return ChatOpenAI(
            model=model or settings.nvidia_model,
            temperature=temperature,
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
    raise ValueError(f"Unknown LLM provider: {provider!r} (expected 'ollama', 'gemini', or 'nvidia')")
