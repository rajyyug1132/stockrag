import os
from functools import lru_cache

from langchain_core.callbacks import BaseCallbackHandler

from stockrag.config import settings


@lru_cache(maxsize=1)
def get_tracing_handler() -> BaseCallbackHandler | None:
    """Langfuse LangChain callback handler, or ``None`` when keys aren't
    configured (local dev without an account, CI) so tracing degrades to a
    no-op instead of failing requests.
    """
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None

    # The langfuse SDK configures itself from the environment; pydantic
    # settings loaded from .env don't reach os.environ on their own.
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)

    from langfuse.langchain import CallbackHandler

    return CallbackHandler()


def tracing_callbacks() -> list[BaseCallbackHandler]:
    handler = get_tracing_handler()
    return [handler] if handler else []
