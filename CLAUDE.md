# StockRAG — project constraints

## LLM providers
- Default provider is `nvidia` (NIM, OpenAI-compatible, `NVIDIA_API_KEY`). Gemini free
  tier caps `gemini-3.5-flash` at 20 req/day — useless for eval; `gemini-2.5-flash`
  404s for new API keys. Ollama stays the fully-local option.
- `moonshotai/kimi-k2.6` is listed by the NIM `/models` endpoint but 404s on invoke
  for this account — don't switch to it.
- NIM retires models with `410 Gone` (`llama-3.3-nemotron-super-49b-v1.5` on
  2026-08-26, `mistral-nemotron` on 2026-09-28). Before switching, check `/models`
  and make a real invoke: `nemotron-3-super-120b-a12b`, `nemotron-nano-3-30b-a3b`,
  `mistral-large-2-instruct` and `llama-3.1-nemotron-70b-instruct` are listed but
  404 for this account.
- Generation model: `minimaxai/minimax-m3.1-flash` (cites per claim, ~4s/answer).
- `nvidia/nemotron-3-ultra-550b-a55b` works but runs 2–4 min/call → Ragas judge
  timeouts. Judge default is `nvidia/nemotron-3.5-lightning-30b-a3b` (<1s/call,
  not yet validated under Ragas). A validated fast judge model is an open TODO.

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

## Model routing (workflow template)
Route each task to the cheapest tier that can do it safely; subagents in
`.claude/agents/` carry the model and effort in their frontmatter.

| Task | Agent | Model @ effort |
| --- | --- | --- |
| Plan a feature, security audit | main session | fable @ high / xhigh |
| Search the codebase | `scout` (read-only) | haiku @ low |
| Renames, boilerplate | main session, inline | read the diff afterwards |
| Build backend from a plan | `builder` | sonnet @ medium |
| Write tests | `test-writer` | sonnet @ low |
| Frontend UI | `ui-builder` | opus @ medium |
| Ingest-token / auth-adjacent code | main session or `debugger` | opus @ xhigh, never haiku |
| Bug that survived one fix attempt | `debugger` | opus @ max |
| Review before commit | `reviewer` | opus @ high |

Standard feature workflow — copy, fill in, run top to bottom:

1. **Locate** — `scout`: where does `<thing>` live, who calls it.
2. **Plan** — main session: files to touch, behaviour, what done looks like.
   Small enough to do in a handful of edits? Do it inline and skip to 5.
3. **Build** — `builder` (backend) or `ui-builder` (frontend) with the plan
   from step 2. Independent backend and frontend halves run in parallel.
4. **Test** — `test-writer` for new behaviour not covered in step 3.
5. **Review** — `reviewer` on the diff. It must be a different model from the
   one that wrote the code.
6. **Gate** — `uv run pytest -q`, `uv run ruff check src tests eval streamlit_ui`;
   regenerate the frozen fixture from the repo root if answers changed.

Rules: route by risk before cost. Raise effort before changing model.
Escalate one tier after one failed attempt, not three. Never switch model
mid-task (the prompt cache is per model) — hand off to a subagent instead.
Always read the diff after mechanical edits.
