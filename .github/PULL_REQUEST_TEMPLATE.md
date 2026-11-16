## What and why

<!-- One or two sentences: what changes, and what problem it solves. -->

## Checklist

- [ ] `uv run pytest -q` passes
- [ ] `uv run ruff check src tests eval streamlit_ui` is clean
- [ ] Frontend changes: `npm run lint` and `npm run build` pass
- [ ] No live LLM or SEC EDGAR calls added to tests or CI
- [ ] If answers changed: frozen fixture regenerated (`--freeze`)
- [ ] README updated if behaviour, commands or config changed
