from dataclasses import dataclass

import tiktoken

from stockrag.config import settings

_ENCODING = tiktoken.get_encoding("cl100k_base")


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

    tokens = _ENCODING.encode(text)
    if not tokens:
        return []

    chunks: list[Chunk] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_tokens, len(tokens))
        chunk_str = _ENCODING.decode(tokens[start:end])
        char_start = len(_ENCODING.decode(tokens[:start]))
        chunks.append(
            Chunk(section=section, text=chunk_str, char_start=char_start, char_end=char_start + len(chunk_str))
        )
        if end == len(tokens):
            break
        start += step
    return chunks
