from functools import lru_cache

import yaml
from langchain_core.prompts import ChatPromptTemplate

from stockrag.config import settings


@lru_cache(maxsize=None)
def load_prompt(version: str = "v1") -> ChatPromptTemplate:
    path = settings.prompts_dir / f"{version}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ChatPromptTemplate.from_messages(
        [
            ("system", data["qa_system"]),
            ("human", data["qa_user"]),
        ]
    )
