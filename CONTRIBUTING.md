# Contributing

Thanks for taking a look. Small, focused changes are easiest to review.

## Setup

Requires [uv](https://docs.astral.sh/uv/) (Python 3.12 is pinned) and Node 20+ for the frontend.

```bash
uv sync
cp .env.example .env   # add NVIDIA_API_KEY (or GEMINI_API_KEY); never commit .env
```

## Before opening a PR

```bash
uv run pytest -q
uv run ruff check src tests eval streamlit_ui
cd frontend && npm run lint && npm run build
```

`master` is protected: the `tests` and `rag-eval` checks must pass and the branch
must be up to date.

## Project rules

- Numbers are computed, never generated: no LLM call on an arithmetic path in `factor_engine/`.
- Answers must pass the citation gate in `src/stockrag/rag/answer.py`.
- CI is fully offline: no live LLM calls and no SEC EDGAR requests in tests or workflows.
- If a change alters answers, regenerate the frozen fixture from the repo root:
  `uv run python eval/run_eval.py --subset smoke --freeze eval/fixtures/smoke_answers.json`
- Keep secrets out of commits. `.env` stays local.
