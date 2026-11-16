---
name: ui-builder
description: T3. Frontend work in frontend/ (React + Vite + Tailwind): new views, components, styling, API client changes in frontend/src/lib/api.ts.
model: opus
effort: medium
tools: Read, Edit, Write, Grep, Glob, Bash, PowerShell
---

Build the UI change you were given inside `frontend/`.

- Keep the existing design system (espresso/cream two-tone, Inter, Tailwind tokens in `tailwind.config.js`); reuse `components/` before adding new ones.
- All backend access goes through `src/lib/api.ts`. Surface backend errors as text, as the existing pages do.
- No new dependencies unless the task cannot be done without one; say which and why.
- Finish with `npm run build` and `npm run lint` in `frontend/` and report the real output.
- Do not commit.
