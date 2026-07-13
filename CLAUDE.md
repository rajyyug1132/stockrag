# StockRAG — project constraints

## LLM providers
- Default provider is `nvidia` (NIM, OpenAI-compatible, `NVIDIA_API_KEY`). Gemini free
  tier caps `gemini-3.5-flash` at 20 req/day — useless for eval; `gemini-2.5-flash`
  404s for new API keys. Ollama stays the fully-local option.
- `moonshotai/kimi-k2.6` is listed by the NIM `/models` endpoint but 404s on invoke
  for this account — don't switch to it.
- `nvidia/nemotron-3-ultra-550b-a55b` works but runs 2–4 min/call → Ragas judge
  timeouts. A faster judge model is an open TODO.

## Environment
- Windows; use `python`, never `python3` (Microsoft Store stub, exit 49).
- `.env` lives only in the repo root (`D:\personal project RAG\.env`), never in
  worktrees and never committed. Run eval/API-key-dependent commands from the repo
  root, not a worktree. Copying `.env` into a worktree is blocked by policy.
- Requires `uv` (Python 3.12 pinned); run everything via `uv run`.

## CI
- `master` is protected: `tests` + `rag-eval` checks must pass, branch up-to-date.
- `rag-eval` is fully offline: it scores the committed frozen fixture
  (`eval/fixtures/smoke_answers.json`) with deterministic metrics only
  (`--frozen ... --no-judge`). No API keys in CI. Live gen+judge there proved
  non-reproducible (free shared endpoints: faithfulness 0.86 -> 0.375 -> 0.0
  on identical inputs) — never re-add live LLM calls to the merge gate.
- After pipeline changes that alter answers, regenerate the fixture locally:
  `uv run python eval/run_eval.py --subset smoke --freeze eval/fixtures/smoke_answers.json`
- Judge metrics (faithfulness/relevancy/precision) are advisory, run locally.
- CI never hits SEC EDGAR (fixture filing only). Keep it that way.
