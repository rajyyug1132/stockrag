# Vercel API entrypoint (project Root Directory = api). Installs the slim deps
# only, so the project needs VECTOR_STORE=supabase, EMBEDDING_PROVIDER=nvidia
# and RERANKER_PROVIDER=nvidia. Regenerate requirements.txt after `uv lock`:
#   uv export --frozen --no-default-groups --no-hashes --no-editable --no-header -o api/requirements.txt
# then change its first line from "." to ".." (the repo root, seen from api/).
import os

# Vercel's filesystem is read-only except /tmp; config.py creates DATA_DIR on import.
os.environ.setdefault("DATA_DIR", "/tmp/stockrag")

from stockrag.api.main import app  # noqa: E402,F401
