# Vercel API entrypoint (project Root Directory = api). api/pyproject.toml
# installs the slim deps only, so the project needs VECTOR_STORE=supabase,
# EMBEDDING_PROVIDER=nvidia and RERANKER_PROVIDER=nvidia.
import os

# Vercel's filesystem is read-only except /tmp; config.py creates DATA_DIR on import.
os.environ.setdefault("DATA_DIR", "/tmp/stockrag")

from stockrag.api.main import app  # noqa: E402,F401
