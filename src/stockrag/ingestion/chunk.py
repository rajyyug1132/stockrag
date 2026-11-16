from dataclasses import dataclass
from functools import lru_cache

import tiktoken

from stockrag.config import settings


@lru_cache(maxsize=1)
def encoding() -> tiktoken.Encoding:
    """cl100k, loaded on first use: the first load fetches the BPE file, which
    importing the API (e.g. a serverless cold start) should not pay for."""
    return tiktoken.get_encoding("cl100k_base")


@dataclass(frozen=True)
class Chunk:
    section: str
    text: str
    char_start: int
    char_end: int


def chunk_text(
    text: str,
    section: str,
    chunk_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> list[Chunk]:
    """Token-aware sliding-window chunking, scoped to a single section so
    chunks never cross a section boundary.
    """
    chunk_tokens = chunk_tokens or settings.chunk_tokens
    overlap_tokens = overlap_tokens or settings.chunk_overlap_tokens
    step = chunk_tokens - overlap_tokens

    enc = encoding()
    tokens = enc.encode(text)
    if not tokens:
        return []

    chunks: list[Chunk] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_tokens, len(tokens))
        chunk_str = enc.decode(tokens[start:end])
        char_start = len(enc.decode(tokens[:start]))
        chunks.append(
            Chunk(section=section, text=chunk_str, char_start=char_start, char_end=char_start + len(chunk_str))
        )
        if end == len(tokens):
            break
        start += step
    return chunks
