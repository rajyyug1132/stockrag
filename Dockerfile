# HF Spaces Docker SDK: builds and runs only the FastAPI backend (src/).
# The frontend/ (Vercel) is a separate deploy target and is excluded via .dockerignore.
FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src
COPY prompts ./prompts

RUN uv sync --frozen --no-dev

# HF Spaces routes traffic to port 7860 by default.
ENV PORT=7860
EXPOSE 7860

# data/ (Chroma, EDGAR cache) is not baked into the image — HF Spaces free tier
# storage is ephemeral, so ingest tickers at runtime via POST /ingest/{ticker}.
CMD ["uv", "run", "uvicorn", "stockrag.api.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "7860"]
