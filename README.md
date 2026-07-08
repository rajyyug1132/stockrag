# StockRAG — Factor Engine + Ask-My-Docs RAG for SEC Filings

Production-grade stock research tooling that automates both halves of the
"How to Research a Company" workflow:

- **Quantitative Factor Engine** — deterministic fundamentals from SEC EDGAR
  XBRL (`companyfacts`), scored against classic factor research: Piotroski
  F-Score (2000), Novy-Marx gross profitability (2013), Fama-French/Carhart
  factor characteristics, plus ROE/net-margin/P-E/P-FCF checks and beta.
- **Qualitative RAG Engine** — 10-K/10-Q ingestion with section-aware
  chunking, hybrid BM25 + vector retrieval (RRF), cross-encoder reranking,
  and citation-enforced answers over ChromaDB, orchestrated with LangChain.

## Architecture

```
              ┌────────────── SEC EDGAR ───────────────┐
              │ company_tickers.json  (ticker→CIK)     │
              │ submissions API       (list filings)   │
              │ Archives              (10-K/10-Q HTML) │
              │ xbrl/companyfacts     (structured nums)│
              └───────┬───────────────────┬────────────┘
                      │ HTML docs         │ XBRL JSON      yfinance
                      v                   v                   │
           ingestion/ (parse→section→chunk)   factor_engine/ <┘
                      │                             │
        rag/embed (bge-small-en-v1.5)               │
                      v                             v
     ChromaDB (persistent) + BM25 ─RRF─> rerank (ms-marco-MiniLM-L-6-v2)
                      │                             │
                      v                             v
     rag/answer (Ollama local / Gemini API)    FactorReport JSON
                      │                             │
        FastAPI: POST /ask, POST /ingest/{ticker}, GET /factors/{ticker}
        CLI (typer): stockrag ingest | ask | factors | retrieve | stats
```

Retrieval is fully local (embeddings + BM25 + reranker all run on CPU).
Only answer generation (and eval judging) can call out — to Gemini, or to a
local Ollama model, switchable per request.

## Setup

Requires [uv](https://docs.astral.sh/uv/) (pins Python 3.12; system 3.14 has
no torch/chromadb wheels yet).

```powershell
uv sync
copy .env.example .env   # fill GEMINI_API_KEY (and optional Langfuse keys)
```

Optional local LLM: install [Ollama](https://ollama.com) and
`ollama pull qwen3:4b`, then use `--llm ollama`.

## Usage

```powershell
# Quantitative: factor report (EDGAR XBRL + yfinance, no LLM involved)
uv run stockrag factors AAPL

# Qualitative: ingest filings, then ask with citations
uv run stockrag ingest AAPL --forms 10-K --years 2
uv run stockrag ask "What are Apple's main risk factors?" AAPL
uv run stockrag ask "..." AAPL --llm ollama          # fully local generation

# Debug retrieval (hybrid+rerank vs pure vector, side by side)
uv run stockrag retrieve "EU state aid decision escrow" AAPL

# SRE metrics over recorded requests
uv run stockrag stats

# API server
uv run uvicorn stockrag.api.main:app --app-dir src
```

Example factor report (AAPL): ROE 152%, net margin 26.9%, beta 1.10,
Piotroski F-Score 8/9, all flowchart checks passing — with explicit
`missing` flags whenever a data source can't supply a field.

## Observability

- **Tracing (Langfuse)** — set `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`
  in `.env` and every request traces retriever, reranker, prompt, and LLM
  spans to [Langfuse Cloud](https://cloud.langfuse.com). Without keys,
  tracing is a silent no-op.
- **Metrics** — every `ask()` appends a JSONL record (stage latencies,
  token usage, cost estimate, citation coverage, refusal/error flags) to
  `data/metrics/requests.jsonl`; `stockrag stats` reports P50/P95 latency,
  refusal/error rates, and cost per request.
- **Versioning** — prompts live in `prompts/v*.yaml` and every response
  echoes its `prompt_version`, so eval results trace back to exact prompt
  configs.

## Evaluation & CI gating

`eval/run_eval.py` runs the full pipeline over a golden QA dataset and
scores it with [Ragas](https://docs.ragas.io) (faithfulness, answer
relevancy, context precision/recall — Gemini judge, local embeddings), plus
two locally computed gates: **citation coverage** (groundedness proxy) and
**refusal accuracy** on deliberately unanswerable questions.

```powershell
uv run python eval/run_eval.py --subset smoke            # 8 questions
uv run python eval/run_eval.py --subset golden           # full set
uv run python eval/run_eval.py --subset smoke --limit 3  # quota-constrained
```

The build fails when any gated metric drops below threshold (faithfulness
≥ 0.75, relevancy ≥ 0.70, precision ≥ 0.60, citation coverage ≥ 0.60,
refusal accuracy ≥ 0.50). GitHub Actions (`.github/workflows/eval.yml`)
runs unit tests on every PR, then ingests a committed filing fixture
(never hitting EDGAR from CI) and runs the smoke eval as a merge gate —
requires the `GEMINI_API_KEY` repo secret.

## Design decisions

- **XBRL over LLM extraction** for financial numbers: deterministic, free,
  multi-year history; the only real work is the priority-ordered tag
  fallback map in `edgar/companyfacts.py`.
- **Section-aware chunking** (650 tokens, 100 overlap, never crossing an
  Item boundary) keeps citations attributable to Item 1A / Item 7 / etc.
- **Local-first retrieval** (bge-small + ms-marco reranker on CPU): zero
  cost and offline; only generation calls out.
- **EDGAR etiquette**: descriptive User-Agent with contact email, ≤8 req/s
  throttle, aggressive disk caching, and no EDGAR traffic from CI.

## Tests

```powershell
uv run pytest -q          # 19 unit tests: chunking, parsing, XBRL, Piotroski, ratios
uv run ruff check src tests eval
```
